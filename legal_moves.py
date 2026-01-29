from board_state import BoardState, Player


def get_legal_moves(board_state: BoardState) -> list[int]:
    """
    Get all legal moves for the current player in the given board state.
    
    A legal move must:
    1. Be on an empty square
    2. Flip at least one opponent piece by sandwiching it between the new piece
       and an existing piece of the current player's color
    
    Args:
        board_state: The current board state
        
    Returns:
        List of legal move positions (0-63, where 0 is top-left, 63 is bottom-right)
    """
    if board_state.next_player == Player.BLACK:
        player_pieces = board_state.black
        opponent_pieces = board_state.white
    else:
        player_pieces = board_state.white
        opponent_pieces = board_state.black
    
    # Empty squares are those not occupied by either player
    occupied = player_pieces | opponent_pieces
    empty_squares = ~occupied & ((1 << 64) - 1)
    
    legal_moves = []
    
    # Check each empty square
    for position in range(64):
        if not (empty_squares & (1 << position)):
            continue
            
        # Check if this position is a legal move
        if is_legal_move(position, player_pieces, opponent_pieces):
            legal_moves.append(position)
    
    return legal_moves


def is_legal_move(position: int, player_pieces: int, opponent_pieces: int) -> bool:
    """
    Check if placing a piece at the given position is legal.
    
    Args:
        position: Position to check (0-63)
        player_pieces: Bitmap of current player's pieces
        opponent_pieces: Bitmap of opponent's pieces
        
    Returns:
        True if the move is legal, False otherwise
    """
    row = position // 8
    col = position % 8
    
    # 8 directions: N, NE, E, SE, S, SW, W, NW
    directions = [
        (-1, 0),   # N
        (-1, 1),   # NE
        (0, 1),    # E
        (1, 1),    # SE
        (1, 0),    # S
        (1, -1),   # SW
        (0, -1),   # W
        (-1, -1),  # NW
    ]
    
    for dr, dc in directions:
        if check_direction(row, col, dr, dc, player_pieces, opponent_pieces):
            return True
    
    return False


def check_direction(row: int, col: int, dr: int, dc: int, 
                    player_pieces: int, opponent_pieces: int) -> bool:
    """
    Check if a move at (row, col) would flip pieces in the given direction.
    
    Args:
        row: Starting row
        col: Starting column
        dr: Row direction (-1, 0, or 1)
        dc: Column direction (-1, 0, or 1)
        player_pieces: Bitmap of current player's pieces
        opponent_pieces: Bitmap of opponent's pieces
        
    Returns:
        True if at least one opponent piece would be flipped in this direction
    """
    r, c = row + dr, col + dc
    found_opponent = False
    
    while 0 <= r < 8 and 0 <= c < 8:
        pos = r * 8 + c
        
        # Check if this position has an opponent piece
        if opponent_pieces & (1 << pos):
            found_opponent = True
            r += dr
            c += dc
        # Check if this position has a player piece
        elif player_pieces & (1 << pos):
            # Only valid if we found at least one opponent piece
            return found_opponent
        else:
            # Empty square - no valid flip in this direction
            return False
    
    # Reached edge of board without finding a player piece
    return False
