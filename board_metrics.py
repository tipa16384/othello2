"""
Board position metrics for post-game LLM analysis.

Each MoveAnalysis captures the board state before and after a move, plus
the delta for all tracked metrics. Metrics are always expressed from
Black's perspective (positive = good for Black).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from board_state import BoardState, Player
from game_utils import DIRECTIONS, notation_to_position, toggle_player
from legal_moves import get_legal_moves
from make_move import make_move
from move_quality import evaluate_legal_move_quality
from strategy_negamax import DEFAULT_WEIGHTS, evaluate

# ── Board geometry constants ────────────────────────────────────────────────

_CORNER_POSITIONS: list[int] = [0, 7, 56, 63]

# X-squares: diagonally adjacent to each corner (worst pre-corner squares)
_X_SQUARE_POSITIONS: list[int] = [9, 14, 49, 54]

# C-squares: orthogonally adjacent to each corner (bad but less so than X)
_C_SQUARE_POSITIONS: list[int] = [1, 8, 6, 15, 48, 57, 55, 62]


# ── Data structures ──────────────────────────────────────────────────────────

@dataclass
class BoardMetrics:
    """Absolute metrics for a board position, from Black's perspective."""
    black_discs: int
    white_discs: int
    black_mobility: int
    white_mobility: int
    black_potential_mobility: int
    white_potential_mobility: int
    black_frontier: int
    white_frontier: int
    black_corners: int
    white_corners: int
    black_x_squares: int
    white_x_squares: int
    black_c_squares: int
    white_c_squares: int
    empty_squares: int
    parity: int          # 0 = even remaining empties, 1 = odd
    eval_score: float    # negamax heuristic, from Black's perspective


@dataclass
class MetricsDelta:
    """Change in metrics (after − before) for a single move."""
    black_discs: int
    white_discs: int
    black_mobility: int
    white_mobility: int
    black_potential_mobility: int
    white_potential_mobility: int
    black_frontier: int
    white_frontier: int
    black_corners: int
    white_corners: int
    black_x_squares: int
    white_x_squares: int
    black_c_squares: int
    white_c_squares: int
    empty_squares: int
    parity: int
    eval_score: float


@dataclass
class MoveAnalysis:
    """Full analysis of one move in a completed game."""
    move_number: int      # 1-based
    notation: str         # e.g. "C4" (black) or "c3" (white)
    player: str           # "black" or "white"
    before: BoardMetrics
    after: BoardMetrics
    delta: MetricsDelta
    corner_taken: bool    # True if this move placed a piece on a corner
    available_moves: int = 0
    good_moves: int = 0
    good_move_ratio: float = 0.0
    chosen_move_is_good: bool = False
    chosen_move_composite_delta: float = 0.0
    best_move_composite_delta: float = 0.0


@dataclass
class Event:
    """Significant event detected on a move."""
    event_type: str
    player: str
    metric: str | None
    owner: str | None
    magnitude: int | float | None
    description: str


@dataclass
class EventWindow:
    """A context window around one or more significant moves."""
    window_id: int
    start_move: int
    end_move: int
    event_move_numbers: list[int]
    moves: list[dict]


# ── Internal helpers ─────────────────────────────────────────────────────────

def _count_at(bitmap: int, positions: list[int]) -> int:
    return sum(1 for p in positions if bitmap & (1 << p))


def _owner_prefix(player: str) -> str:
    return "black" if player == Player.BLACK.value else "white"


def _square_list(bitmap: int) -> list[str]:
    squares: list[str] = []
    for position in range(64):
        if bitmap & (1 << position):
            row = position // 8
            col = position % 8
            squares.append(f"{chr(ord('A') + col)}{row + 1}")
    return squares


def _corner_for_risky_square(position: int) -> int | None:
    mapping = {
        9: 0,
        14: 7,
        49: 56,
        54: 63,
        1: 0,
        8: 0,
        6: 7,
        15: 7,
        48: 56,
        57: 56,
        55: 63,
        62: 63,
    }
    return mapping.get(position)


def _event_dicts(events: list[Event]) -> list[dict]:
    return [asdict(event) for event in events]


def _frontier_count(player_pieces: int, all_pieces: int) -> int:
    """Count player's frontier discs (discs adjacent to at least one empty square)."""
    empty = ~all_pieces & 0xFFFFFFFFFFFFFFFF
    count = 0
    bits = player_pieces
    while bits:
        lsb = bits & -bits
        pos = lsb.bit_length() - 1
        row, col = divmod(pos, 8)
        for dr, dc in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < 8 and 0 <= nc < 8 and (empty >> (nr * 8 + nc)) & 1:
                count += 1
                break   # this disc is frontier; no need to check further neighbors
        bits ^= lsb
    return count


def _potential_mobility_count(opponent_pieces: int, all_pieces: int) -> int:
    """Count distinct empty squares adjacent to any opponent piece.

    These are the squares a player *could* potentially reach, giving a proxy
    for future mobility pressure.
    """
    empty = ~all_pieces & 0xFFFFFFFFFFFFFFFF
    reachable = 0
    bits = opponent_pieces
    while bits:
        lsb = bits & -bits
        pos = lsb.bit_length() - 1
        row, col = divmod(pos, 8)
        for dr, dc in DIRECTIONS:
            nr, nc = row + dr, col + dc
            if 0 <= nr < 8 and 0 <= nc < 8:
                nbit = 1 << (nr * 8 + nc)
                if empty & nbit:
                    reachable |= nbit
        bits ^= lsb
    return reachable.bit_count()


def _make_board(base: BoardState, next_player: Player) -> BoardState:
    return BoardState(
        user=base.user,
        black=base.black,
        white=base.white,
        next_player=next_player,
        session_id=base.session_id,
    )


def _eval_from_black(board_state: BoardState, weights: dict) -> float:
    """Return the negamax heuristic score always from Black's perspective."""
    score = evaluate(board_state, weights)
    return score if board_state.next_player == Player.BLACK else -score


def _delta(before: BoardMetrics, after: BoardMetrics) -> MetricsDelta:
    return MetricsDelta(
        black_discs=after.black_discs - before.black_discs,
        white_discs=after.white_discs - before.white_discs,
        black_mobility=after.black_mobility - before.black_mobility,
        white_mobility=after.white_mobility - before.white_mobility,
        black_potential_mobility=after.black_potential_mobility - before.black_potential_mobility,
        white_potential_mobility=after.white_potential_mobility - before.white_potential_mobility,
        black_frontier=after.black_frontier - before.black_frontier,
        white_frontier=after.white_frontier - before.white_frontier,
        black_corners=after.black_corners - before.black_corners,
        white_corners=after.white_corners - before.white_corners,
        black_x_squares=after.black_x_squares - before.black_x_squares,
        white_x_squares=after.white_x_squares - before.white_x_squares,
        black_c_squares=after.black_c_squares - before.black_c_squares,
        white_c_squares=after.white_c_squares - before.white_c_squares,
        empty_squares=after.empty_squares - before.empty_squares,
        parity=after.parity - before.parity,
        eval_score=after.eval_score - before.eval_score,
    )


def _board_snapshot(board_state: BoardState) -> dict:
    return {
        "next_player": board_state.next_player.value,
        "black_squares": _square_list(board_state.black),
        "white_squares": _square_list(board_state.white),
    }


def _move_owner_delta(move: MoveAnalysis, metric: str, owner: str) -> int | float:
    value = getattr(move.delta, f"{owner}_{metric}")
    return value


def _drastic_thresholds() -> dict[str, int | float]:
    return {
        "mobility": 4,
        "frontier": 6,
        "discs": 7,
        "potential_mobility": 7,
        "eval_score": 120.0,
        # Composite delta for move quality: eval + mobility/frontier/potential/etc.
        "good_move_composite_delta": 10.0,
    }


def _detect_events(move: MoveAnalysis, before_board: BoardState) -> list[Event]:
    events: list[Event] = []
    thresholds = _drastic_thresholds()
    mover = move.player
    mover_prefix = _owner_prefix(mover)
    position = notation_to_position(move.notation)

    if move.corner_taken:
        events.append(Event(
            event_type="corner_taken",
            player=mover,
            metric="corners",
            owner=mover,
            magnitude=1,
            description=f"{mover.title()} took corner {move.notation.upper()}.",
        ))

    risky_corner = _corner_for_risky_square(position)
    if risky_corner is not None and not ((before_board.black | before_board.white) & (1 << risky_corner)):
        risky_type = "x_square_open_corner" if position in _X_SQUARE_POSITIONS else "c_square_open_corner"
        events.append(Event(
            event_type=risky_type,
            player=mover,
            metric="square_risk",
            owner=mover,
            magnitude=1,
            description=(
                f"{mover.title()} moved to {move.notation.upper()} while the adjacent corner "
                f"{_square_list(1 << risky_corner)[0]} was still open."
            ),
        ))

    mover_mobility_delta = _move_owner_delta(move, "mobility", mover_prefix)
    if abs(mover_mobility_delta) >= thresholds["mobility"]:
        direction = "increased" if mover_mobility_delta > 0 else "dropped"
        events.append(Event(
            event_type="mobility_swing",
            player=mover,
            metric="mobility",
            owner=mover,
            magnitude=abs(mover_mobility_delta),
            description=f"{mover.title()} mobility {direction} by {abs(mover_mobility_delta)}.",
        ))

    opponent = "white" if mover == "black" else "black"
    opponent_mobility_delta = _move_owner_delta(move, "mobility", opponent)
    if abs(opponent_mobility_delta) >= thresholds["mobility"]:
        direction = "increased" if opponent_mobility_delta > 0 else "dropped"
        events.append(Event(
            event_type="opponent_mobility_swing",
            player=mover,
            metric="mobility",
            owner=opponent,
            magnitude=abs(opponent_mobility_delta),
            description=f"{opponent.title()} mobility {direction} by {abs(opponent_mobility_delta)}.",
        ))

    for owner in ("black", "white"):
        frontier_delta = _move_owner_delta(move, "frontier", owner)
        if abs(frontier_delta) >= thresholds["frontier"]:
            direction = "increased" if frontier_delta > 0 else "dropped"
            events.append(Event(
                event_type="frontier_swing",
                player=mover,
                metric="frontier",
                owner=owner,
                magnitude=abs(frontier_delta),
                description=f"{owner.title()} frontier {direction} by {abs(frontier_delta)}.",
            ))

    for owner in ("black", "white"):
        disc_delta = _move_owner_delta(move, "discs", owner)
        if abs(disc_delta) >= thresholds["discs"]:
            direction = "increased" if disc_delta > 0 else "dropped"
            events.append(Event(
                event_type="disc_swing",
                player=mover,
                metric="discs",
                owner=owner,
                magnitude=abs(disc_delta),
                description=f"{owner.title()} disc count {direction} by {abs(disc_delta)}.",
            ))

    for owner in ("black", "white"):
        potential_delta = _move_owner_delta(move, "potential_mobility", owner)
        if abs(potential_delta) >= thresholds["potential_mobility"]:
            direction = "increased" if potential_delta > 0 else "dropped"
            events.append(Event(
                event_type="potential_mobility_swing",
                player=mover,
                metric="potential_mobility",
                owner=owner,
                magnitude=abs(potential_delta),
                description=f"{owner.title()} potential mobility {direction} by {abs(potential_delta)}.",
            ))

    if abs(move.delta.eval_score) >= thresholds["eval_score"]:
        direction = "improved" if move.delta.eval_score > 0 else "worsened"
        beneficiary = "Black" if move.delta.eval_score > 0 else "White"
        events.append(Event(
            event_type="eval_swing",
            player=mover,
            metric="eval_score",
            owner="black_perspective",
            magnitude=round(abs(move.delta.eval_score), 2),
            description=f"Evaluation {direction} for {beneficiary} by {abs(move.delta.eval_score):.2f}.",
        ))

    return events


def _serialize_move(move: MoveAnalysis, before_board: BoardState, after_board: BoardState, events: list[Event]) -> dict:
    return {
        "move_number": move.move_number,
        "notation": move.notation,
        "player": move.player,
        "before": {
            "board": _board_snapshot(before_board),
            "metrics": asdict(move.before),
        },
        "after": {
            "board": _board_snapshot(after_board),
            "metrics": asdict(move.after),
        },
        "delta": asdict(move.delta),
        "corner_taken": move.corner_taken,
        "available_moves": move.available_moves,
        "good_moves": move.good_moves,
        "good_move_ratio": round(move.good_move_ratio, 4),
        "chosen_move_is_good": move.chosen_move_is_good,
        "chosen_move_composite_delta": round(move.chosen_move_composite_delta, 4),
        "best_move_composite_delta": round(move.best_move_composite_delta, 4),
        "events": _event_dicts(events),
        "is_event_move": bool(events),
    }


def _replay_positions(
    move_record: str,
    weights: dict,
    user: str,
    opening_ended: dict | None = None,
) -> list[tuple[MoveAnalysis, BoardState, BoardState, list[Event]]]:
    analyses = analyze_game(move_record, weights=weights, user=user)
    board = BoardState(user=user)
    replayed: list[tuple[MoveAnalysis, BoardState, BoardState, list[Event]]] = []

    for move in analyses:
        intended_player = Player.BLACK if move.player == Player.BLACK.value else Player.WHITE
        if board.next_player != intended_player:
            board = make_move(None, board)

        before_board = _make_board(board, board.next_player)
        position = notation_to_position(move.notation)
        after_board = make_move(position, board)
        events = _detect_events(move, before_board)

        if (
            opening_ended
            and move.move_number == opening_ended["move_number"]
            and opening_ended.get("opening_name")
        ):
            opening_name = opening_ended["opening_name"]
            events = [Event(
                event_type="opening_ended",
                player=move.player,
                metric="opening",
                owner=move.player,
                magnitude=move.move_number,
                description=f"{move.player.title()} played the first move outside the {opening_name} opening.",
            )] + events

        replayed.append((move, before_board, after_board, events))
        board = after_board

    if replayed:
        move, before_board, after_board, events = replayed[-1]
        endgame_event = Event(
            event_type="end_of_game",
            player=move.player,
            metric="game_phase",
            owner="game",
            magnitude=move.move_number,
            description=f"Game ended after move {move.move_number} ({move.notation}).",
        )
        replayed[-1] = (move, before_board, after_board, [endgame_event] + events)

    return replayed


def _group_event_windows(
    replayed: list[tuple[MoveAnalysis, BoardState, BoardState, list[Event]]],
    radius: int,
) -> list[tuple[int, int, list[int]]]:
    event_indices = [index for index, (_, _, _, events) in enumerate(replayed) if events]
    if not event_indices:
        return []

    grouped: list[tuple[int, int, list[int]]] = []
    current_start = max(0, event_indices[0] - radius)
    current_end = min(len(replayed) - 1, event_indices[0] + radius)
    current_events = [event_indices[0]]

    for index in event_indices[1:]:
        start = max(0, index - radius)
        end = min(len(replayed) - 1, index + radius)
        if start <= current_end:
            current_end = max(current_end, end)
            current_events.append(index)
        else:
            grouped.append((current_start, current_end, current_events))
            current_start = start
            current_end = end
            current_events = [index]

    grouped.append((current_start, current_end, current_events))
    return grouped


# ── Public API ───────────────────────────────────────────────────────────────

def compute_metrics(board_state: BoardState, weights: dict | None = None) -> BoardMetrics:
    """Compute all position metrics for a board state, from Black's perspective."""
    if weights is None:
        weights = DEFAULT_WEIGHTS

    black = board_state.black
    white = board_state.white
    all_pieces = black | white

    black_discs = black.bit_count()
    white_discs = white.bit_count()
    empty_squares = 64 - black_discs - white_discs

    black_board = _make_board(board_state, Player.BLACK)
    white_board = _make_board(board_state, Player.WHITE)

    return BoardMetrics(
        black_discs=black_discs,
        white_discs=white_discs,
        black_mobility=len(get_legal_moves(black_board)),
        white_mobility=len(get_legal_moves(white_board)),
        black_potential_mobility=_potential_mobility_count(white, all_pieces),
        white_potential_mobility=_potential_mobility_count(black, all_pieces),
        black_frontier=_frontier_count(black, all_pieces),
        white_frontier=_frontier_count(white, all_pieces),
        black_corners=_count_at(black, _CORNER_POSITIONS),
        white_corners=_count_at(white, _CORNER_POSITIONS),
        black_x_squares=_count_at(black, _X_SQUARE_POSITIONS),
        white_x_squares=_count_at(white, _X_SQUARE_POSITIONS),
        black_c_squares=_count_at(black, _C_SQUARE_POSITIONS),
        white_c_squares=_count_at(white, _C_SQUARE_POSITIONS),
        empty_squares=empty_squares,
        parity=empty_squares % 2,
        eval_score=_eval_from_black(board_state, weights),
    )


def analyze_game(
    move_record: str,
    weights: dict | None = None,
    user: str = "analysis",
) -> list[MoveAnalysis]:
    """Replay a completed game from its move record and return per-move analysis.

    Args:
        move_record: Sequence of 2-character move tokens, uppercase = Black,
                     lowercase = White (e.g. "C4c3D3...").
        weights:     Negamax evaluation weights (defaults to DEFAULT_WEIGHTS).
        user:        User label for the scratch BoardState objects.

    Returns:
        One MoveAnalysis per move in the record.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    if len(move_record) % 2 != 0:
        raise ValueError(f"move_record length must be even, got {len(move_record)}")

    tokens = [move_record[i:i+2] for i in range(0, len(move_record), 2)]
    board = BoardState(user=user)
    analyses: list[MoveAnalysis] = []

    for move_number, token in enumerate(tokens, start=1):
        intended_player = Player.BLACK if token[0].isupper() else Player.WHITE

        # If the board's next player doesn't match, the other player had to pass.
        if board.next_player != intended_player:
            board = make_move(None, board)

        position = notation_to_position(token)
        before = compute_metrics(board, weights)
        good_move_threshold = _drastic_thresholds()["good_move_composite_delta"]
        quality = evaluate_legal_move_quality(
            board,
            weights=weights,
            good_move_threshold=good_move_threshold,
        )
        move_delta_by_position = quality["move_delta_by_position"]
        good_moves = quality["good_moves"]
        available_moves = quality["available_moves"]
        good_move_ratio = quality["good_move_ratio"]
        chosen_move_composite_delta = move_delta_by_position.get(position, float("-inf"))
        chosen_move_is_good = chosen_move_composite_delta >= good_move_threshold
        best_move_composite_delta = quality["best_move_composite_delta"]

        board = make_move(position, board)
        after = compute_metrics(board, weights)

        analyses.append(MoveAnalysis(
            move_number=move_number,
            notation=token,
            player=intended_player.value,
            before=before,
            after=after,
            delta=_delta(before, after),
            corner_taken=(
                _count_at(1 << position, _CORNER_POSITIONS) == 1
            ),
            available_moves=available_moves,
            good_moves=good_moves,
            good_move_ratio=good_move_ratio,
            chosen_move_is_good=chosen_move_is_good,
            chosen_move_composite_delta=chosen_move_composite_delta,
            best_move_composite_delta=best_move_composite_delta,
        ))

    return analyses


def extract_event_windows(
    move_record: str,
    weights: dict | None = None,
    user: str = "analysis",
    radius: int = 2,
    opening_ended: dict | None = None,
) -> dict:
    """Return JSON-serializable event windows around significant moves.

    Args:
        opening_ended: Optional dict with ``move_number`` (int) and
                       ``opening_name`` (str) to inject an ``opening_ended``
                       event at the first move played outside the opening book.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    replayed = _replay_positions(move_record, weights=weights, user=user, opening_ended=opening_ended)
    grouped = _group_event_windows(replayed, radius)

    windows: list[EventWindow] = []
    for window_id, (start, end, event_indices) in enumerate(grouped, start=1):
        moves: list[dict] = []
        for replay_index in range(start, end + 1):
            move, before_board, after_board, events = replayed[replay_index]
            moves.append(_serialize_move(move, before_board, after_board, events))

        windows.append(EventWindow(
            window_id=window_id,
            start_move=replayed[start][0].move_number,
            end_move=replayed[end][0].move_number,
            event_move_numbers=[replayed[index][0].move_number for index in event_indices],
            moves=moves,
        ))

    return {
        "move_record": move_record,
        "window_radius": radius,
        "event_thresholds": _drastic_thresholds(),
        "windows": [asdict(window) for window in windows],
    }


def write_event_windows_json(
    move_record: str,
    output_path: str,
    weights: dict | None = None,
    user: str = "analysis",
    radius: int = 2,
) -> dict:
    """Write event windows to JSON and return the payload."""
    payload = extract_event_windows(
        move_record=move_record,
        weights=weights,
        user=user,
        radius=radius,
    )
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return payload
