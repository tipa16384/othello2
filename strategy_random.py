import random

from board_state import BoardState
from legal_moves import get_legal_moves


def choose_move(board_state: BoardState) -> int | None:
    """
    Choose a random legal move for the current player.

    Args:
        board_state: Current board state

    Returns:
        A randomly chosen legal move (0-63), or None if no legal moves exist
    """
    legal_moves = get_legal_moves(board_state)
    if not legal_moves:
        return None

    return random.choice(legal_moves)
