import random

from board_state import BoardState
from legal_moves import get_legal_moves
from make_move import make_move


def choose_move(board_state: BoardState) -> int | None:
    """
    Choose a move that minimizes the opponent's legal moves.
    
    This "strangle" strategy evaluates each legal move by applying it and
    counting how many legal moves the opponent would have in response.
    It selects the move that leaves the opponent with the fewest options.
    If multiple moves tie for the minimum, one is chosen randomly.

    Args:
        board_state: Current board state

    Returns:
        The chosen move (0-63), or None if no legal moves exist
    """
    legal_moves = get_legal_moves(board_state)
    if not legal_moves:
        return None

    best_moves = []
    min_opponent_moves = float('inf')

    for move in legal_moves:
        # Apply the move and see how many moves the opponent would have
        new_board = make_move(move, board_state)
        opponent_moves = get_legal_moves(new_board)
        opponent_count = len(opponent_moves)

        if opponent_count < min_opponent_moves:
            # Found a better move - reset the list
            min_opponent_moves = opponent_count
            best_moves = [move]
        elif opponent_count == min_opponent_moves:
            # Tied with the best - add to list
            best_moves.append(move)

    return random.choice(best_moves)
