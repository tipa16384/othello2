from __future__ import annotations

from typing import Any

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move


def composite_metric_score(metrics: Any, player: Player) -> float:
    """Compute the enhanced one-ply move-quality score for the given player."""
    if player == Player.BLACK:
        own_mobility = metrics.black_mobility
        opp_mobility = metrics.white_mobility
        own_potential = metrics.black_potential_mobility
        opp_potential = metrics.white_potential_mobility
        own_frontier = metrics.black_frontier
        opp_frontier = metrics.white_frontier
        own_corners = metrics.black_corners
        opp_corners = metrics.white_corners
        own_x = metrics.black_x_squares
        opp_x = metrics.white_x_squares
        own_c = metrics.black_c_squares
        opp_c = metrics.white_c_squares
        own_discs = metrics.black_discs
        opp_discs = metrics.white_discs
        eval_for_player = metrics.eval_score
    else:
        own_mobility = metrics.white_mobility
        opp_mobility = metrics.black_mobility
        own_potential = metrics.white_potential_mobility
        opp_potential = metrics.black_potential_mobility
        own_frontier = metrics.white_frontier
        opp_frontier = metrics.black_frontier
        own_corners = metrics.white_corners
        opp_corners = metrics.black_corners
        own_x = metrics.white_x_squares
        opp_x = metrics.black_x_squares
        own_c = metrics.white_c_squares
        opp_c = metrics.black_c_squares
        own_discs = metrics.white_discs
        opp_discs = metrics.black_discs
        eval_for_player = -metrics.eval_score

    mobility_edge = own_mobility - opp_mobility
    potential_edge = own_potential - opp_potential
    frontier_edge = opp_frontier - own_frontier
    corner_edge = own_corners - opp_corners
    risk_edge = (opp_x - own_x) + (opp_c - own_c)
    disc_edge = own_discs - opp_discs

    parity_bonus = 1.0 if metrics.parity == 1 else 0.0

    return (
        eval_for_player
        + 4.0 * mobility_edge
        + 2.0 * potential_edge
        + 2.0 * frontier_edge
        + 20.0 * corner_edge
        + 4.0 * risk_edge
        + 0.5 * disc_edge
        + 1.0 * parity_bonus
    )


def evaluate_legal_move_quality(
    board_state: BoardState,
    *,
    weights: dict,
    good_move_threshold: float,
) -> dict[str, Any]:
    """Evaluate legal moves by composite delta and return summary stats."""
    # Local import avoids a module cycle: board_metrics imports this module.
    from board_metrics import compute_metrics

    legal_moves = get_legal_moves(board_state)
    move_delta_by_position: dict[int, float] = {}

    if legal_moves:
        before_metrics = compute_metrics(board_state, weights)
        pre_composite_score = composite_metric_score(before_metrics, board_state.next_player)

        for legal_position in legal_moves:
            candidate_after_board = make_move(legal_position, board_state)
            candidate_after_metrics = compute_metrics(candidate_after_board, weights)
            candidate_composite_score = composite_metric_score(candidate_after_metrics, board_state.next_player)
            move_delta_by_position[legal_position] = candidate_composite_score - pre_composite_score

    good_moves = sum(
        1 for candidate_delta in move_delta_by_position.values()
        if candidate_delta >= good_move_threshold
    )
    available_moves = len(legal_moves)
    good_move_ratio = (good_moves / available_moves) if available_moves else 0.0
    best_move_composite_delta = max(move_delta_by_position.values()) if move_delta_by_position else float("-inf")

    return {
        "available_moves": available_moves,
        "good_moves": good_moves,
        "good_move_ratio": good_move_ratio,
        "best_move_composite_delta": best_move_composite_delta,
        "move_delta_by_position": move_delta_by_position,
    }
