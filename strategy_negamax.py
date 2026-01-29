import random

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move


# Default evaluation weights
DEFAULT_WEIGHTS = {
    'mobility': 20.585377749475168,
    'corners': 98.72636463496178,
    'corner_adjacent': 43.89928663721947,
    'edges': 8.557803407573122,
    'piece_count': 2.0084825493628227,
}


def choose_move(board_state: BoardState, depth: int = 4, weights: dict | None = None) -> int | None:
    """
    Choose a move using negamax algorithm with alpha-beta pruning.
    
    Args:
        board_state: Current board state
        depth: Maximum search depth (default: 4)
        weights: Dictionary of evaluation weights (default: DEFAULT_WEIGHTS)
    
    Returns:
        The chosen move (0-63), or None if no legal moves exist
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS
    
    legal_moves = get_legal_moves(board_state)
    if not legal_moves:
        return None
    
    best_moves = []
    best_score = float('-inf')
    alpha = float('-inf')
    beta = float('inf')
    
    for move in legal_moves:
        new_board = make_move(move, board_state)
        # Negamax returns score from current player's perspective
        # We negate it since we're evaluating opponent's position
        score = -negamax(new_board, depth - 1, -beta, -alpha, weights)
        
        if score > best_score:
            best_score = score
            best_moves = [move]
            alpha = max(alpha, score)
        elif score == best_score:
            best_moves.append(move)
    
    return random.choice(best_moves)


def negamax(board_state: BoardState, depth: int, alpha: float, beta: float, weights: dict) -> float:
    """
    Negamax algorithm with alpha-beta pruning.
    
    Args:
        board_state: Current board state
        depth: Remaining search depth
        alpha: Alpha value for pruning
        beta: Beta value for pruning
        weights: Dictionary of evaluation weights
    
    Returns:
        Score from current player's perspective
    """
    legal_moves = get_legal_moves(board_state)
    
    # Terminal conditions
    if depth == 0:
        return evaluate(board_state, weights)
    
    # Check for game over (no moves for either player)
    if not legal_moves:
        # Pass to opponent
        new_board = make_move(None, board_state)
        opponent_moves = get_legal_moves(new_board)
        
        if not opponent_moves:
            # Game over - evaluate final position
            return evaluate_final(board_state)
        else:
            # Opponent can move after pass
            return -negamax(new_board, depth, -beta, -alpha, weights)
    
    max_score = float('-inf')
    
    for move in legal_moves:
        new_board = make_move(move, board_state)
        score = -negamax(new_board, depth - 1, -beta, -alpha, weights)
        
        max_score = max(max_score, score)
        alpha = max(alpha, score)
        
        if alpha >= beta:
            break  # Beta cutoff
    
    return max_score


def evaluate(board_state: BoardState, weights: dict) -> float:
    """
    Evaluate a board position from the current player's perspective.
    
    Uses a combination of factors:
    - Mobility (number of legal moves)
    - Corner control (very valuable)
    - Dangerous squares adjacent to empty corners (heavily penalized)
    - Edge control
    - Piece count (weighted less early in game)
    
    Args:
        board_state: Board state to evaluate
        weights: Dictionary of evaluation weights
    
    Returns:
        Score from current player's perspective (positive is better)
    """
    if board_state.next_player == Player.BLACK:
        player_pieces = board_state.black
        opponent_pieces = board_state.white
    else:
        player_pieces = board_state.white
        opponent_pieces = board_state.black
    
    score = 0.0
    
    # Mobility - number of legal moves
    player_mobility = len(get_legal_moves(board_state))
    # Create temporary board with opponent as next player
    temp_board = BoardState(
        user=board_state.user,
        black=board_state.black,
        white=board_state.white,
        next_player=Player.WHITE if board_state.next_player == Player.BLACK else Player.BLACK,
        session_id=board_state.session_id
    )
    opponent_mobility = len(get_legal_moves(temp_board))
    
    if player_mobility + opponent_mobility != 0:
        score += weights['mobility'] * (player_mobility - opponent_mobility)
    
    # Corner control (corners are extremely valuable)
    corners = [0, 7, 56, 63]
    player_corners = sum(1 for c in corners if player_pieces & (1 << c))
    opponent_corners = sum(1 for c in corners if opponent_pieces & (1 << c))
    score += weights['corners'] * (player_corners - opponent_corners)
    
    # Dangerous squares adjacent to corners (X-squares and C-squares)
    # Only penalize if the corner is empty
    corner_adjacent = {
        0: [1, 8, 9],      # Top-left corner
        7: [6, 14, 15],    # Top-right corner
        56: [48, 49, 57],  # Bottom-left corner
        63: [54, 55, 62]   # Bottom-right corner
    }
    
    for corner, adjacent in corner_adjacent.items():
        corner_occupied = (player_pieces | opponent_pieces) & (1 << corner)
        if not corner_occupied:  # Corner is empty
            for adj in adjacent:
                if player_pieces & (1 << adj):
                    score -= weights['corner_adjacent']  # Heavy penalty for occupying square next to empty corner
                if opponent_pieces & (1 << adj):
                    score += weights['corner_adjacent']  # Bonus if opponent made this mistake
    
    # Edge control (edges are valuable if you control the corner or it's occupied)
    edges = [1, 2, 3, 4, 5, 6, 8, 16, 24, 32, 40, 48, 15, 23, 31, 39, 47, 55, 57, 58, 59, 60, 61, 62]
    player_edges = sum(1 for e in edges if player_pieces & (1 << e))
    opponent_edges = sum(1 for e in edges if opponent_pieces & (1 << e))
    score += weights['edges'] * (player_edges - opponent_edges)
    
    # Piece count (matters more in endgame)
    total_pieces = bin(player_pieces | opponent_pieces).count('1')
    piece_weight = total_pieces / 64.0  # Increases as game progresses
    player_count = bin(player_pieces).count('1')
    opponent_count = bin(opponent_pieces).count('1')
    score += piece_weight * weights['piece_count'] * (player_count - opponent_count)
    
    return score


def evaluate_final(board_state: BoardState) -> float:
    """
    Evaluate a final game position.
    
    Args:
        board_state: Final board state
    
    Returns:
        Large positive score if current player wins, large negative if loses, 0 for draw
    """
    if board_state.next_player == Player.BLACK:
        player_pieces = board_state.black
        opponent_pieces = board_state.white
    else:
        player_pieces = board_state.white
        opponent_pieces = board_state.black
    
    player_count = bin(player_pieces).count('1')
    opponent_count = bin(opponent_pieces).count('1')
    
    if player_count > opponent_count:
        return 1000.0
    elif player_count < opponent_count:
        return -1000.0
    else:
        return 0.0
