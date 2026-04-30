import random

from board_state import BoardState
from move_quality import evaluate_legal_move_quality
from strategy_negamax import DEFAULT_WEIGHTS


def choose_move(
    board_state: BoardState,
    minimum_good_delta: float = 10.0,
    weights: dict | None = None,
) -> int | None:
    """Choose a move using only one-ply enhanced composite evaluation."""
    if weights is None:
        weights = DEFAULT_WEIGHTS

    quality = evaluate_legal_move_quality(
        board_state,
        weights=weights,
        good_move_threshold=minimum_good_delta,
    )
    deltas: dict[int, float] = quality["move_delta_by_position"]
    if not deltas:
        return None

    best_delta = max(deltas.values())
    best_moves = [move for move, delta in deltas.items() if delta == best_delta]
    return random.choice(best_moves)
