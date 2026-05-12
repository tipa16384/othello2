from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from pathlib import Path
import random

from board_state import BoardState, Player
from game_utils import (
    OPPONENT_PROFILES,
    counts_for_user,
    notation_to_position,
    position_to_notation,
)
from legal_moves import get_legal_moves
from make_move import make_move
from openings import openings
from board_metrics import extract_event_windows
import strategy_april
import strategy_negamax
import strategy_mcts

from api.game_session import GameSession


@dataclass(frozen=True)
class OpponentConfig:
    name: str
    portrait: str
    strategy: str
    parameter: int
    use_opening_book: bool


_OPPONENTS_BY_LEVEL: dict[int, OpponentConfig] = {
    level: OpponentConfig(name, portrait, strategy, parameter, use_opening_book)
    for level, (name, portrait, strategy, parameter, use_opening_book) in enumerate(OPPONENT_PROFILES, start=1)
}


_OPPONENT_PHRASES: dict[str, dict[str, str]] = {
    "Michelangelo": {
        "start": "Let's go, dudes!",
        "win": "Booyakasha! I win!",
        "lose": "Aw man... pizza break?",
        "draw": "Tie? Still fun!",
    },
    "Raphael": {
        "start": "Alright, let's do this.",
        "win": "Yeah! That's how it's done.",
        "lose": "Tch. Lucky.",
        "draw": "Whatever. Call it even.",
    },
    "Leonardo": {
        "start": "Focus. Begin.",
        "win": "Victory is mine.",
        "lose": "I need more practice.",
        "draw": "A balanced match.",
    },
    "Donatello": {
        "start": "Analyzing board... go.",
        "win": "Optimal play confirmed.",
        "lose": "Unexpected outcome.",
        "draw": "Statistically equal.",
    },
    "Shredder": {
        "start": "Kneel before your better.",
        "win": "Pathetic. You never stood a chance.",
        "lose": "This is not over.",
        "draw": "A temporary stalemate.",
    },
    "April": {
        "start": "Let's test the strongest immediate move.",
        "win": "See? Clean tactics can win.",
        "lose": "Okay, that looked better one move ago.",
        "draw": "Even game. I'll take the data point.",
    },
}


_ROOT_DIR = Path(__file__).resolve().parent.parent


def _game_log_dir() -> Path:
    configured = os.environ.get("OTHELLO_GAMELOG_DIR")
    if configured:
        return Path(configured)
    return _ROOT_DIR / "gamelogs"


def _participant_label(kind: str, name: str, strategy: str | None = None, parameter: int | None = None) -> str:
    if kind == "player":
        return f'Player "{name}"'
    if strategy == "negamax":
        return f"Negamax depth {parameter} ({name})"
    if strategy == "mcts":
        return f"MCTS {parameter} ({name})"
    if strategy == "april":
        return f"April one-ply ({name})"
    if strategy and parameter is not None:
        return f"{strategy} {parameter} ({name})"
    return name


def _write_game_log_if_needed(session: GameSession) -> None:
    if session.game_log_path is not None:
        return

    log_dir = _game_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    output_path = log_dir / f"{timestamp}_{session.game_id}.json"

    player_label = _participant_label("player", session.player_name)
    computer_label = _participant_label(
        "computer",
        session.opponent_name,
        session.ai_strategy,
        session.ai_parameter,
    )
    black_player = player_label if session.user_color == Player.BLACK else computer_label
    white_player = player_label if session.user_color == Player.WHITE else computer_label

    opening_ended = None
    if session.opening_book_exhausted and session.opening_name_used and session.opening_book_exhausted_at_move:
        opening_ended = {
            "move_number": session.opening_book_exhausted_at_move,
            "opening_name": session.opening_name_used,
        }

    payload = extract_event_windows(session.move_record, user=session.player_name, radius=2, opening_ended=opening_ended)
    payload.update({
        "game_id": session.game_id,
        "player_name": session.player_name,
        "player_color": session.user_color.value,
        "ai_color": session.computer_color.value,
        "ai_name": session.opponent_name,
        "ai_level": session.ai_level,
        "ai_strategy": session.ai_strategy,
        "ai_parameter": session.ai_parameter,
        "black_player": black_player,
        "white_player": white_player,
        "winner": session.winner,
        "game_over": session.game_over,
        "move_count": len(session.move_record) // 2,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    })

    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    session.game_log_path = str(output_path)


def _opponent_phrase(session: GameSession, key: str) -> str:
    return _OPPONENT_PHRASES.get(session.opponent_name, {}).get(key, "")


def _board_to_cells(board_state: BoardState) -> list[str]:
    cells: list[str] = []
    for pos in range(64):
        mask = 1 << pos
        if board_state.black & mask:
            cells.append("black")
        elif board_state.white & mask:
            cells.append("white")
        else:
            cells.append("empty")
    return cells


def _counts(board_state: BoardState, user_color: Player) -> tuple[int, int, int, int]:
    return counts_for_user(board_state, user_color)


def _append_final_score(session: GameSession) -> None:
    black_count, white_count, _, _ = _counts(session.board_state, session.user_color)
    session.messages.append(f"Final score - Black: {black_count}, White: {white_count}")


def _append_move_record(session: GameSession, move: int, mover_color: Player) -> None:
    notation = position_to_notation(move)
    file_letter = notation[0].upper() if mover_color == Player.BLACK else notation[0].lower()
    session.move_record += f"{file_letter}{notation[1:]}"


def _opening_hints_for_moves(session: GameSession, legal_moves: list[int]) -> dict[int, str]:
    """Return {position: shortest_opening_name} for legal moves that continue an opening.

    Skipped for move 0 (black's first move) because every opening would match.
    """
    if session.move_number == 0 or session.opening_book_exhausted:
        return {}

    history = session.move_record
    is_black_turn = session.board_state.next_player == Player.BLACK
    hints: dict[int, str] = {}

    for pos in legal_moves:
        notation = position_to_notation(pos)
        # Opening book uses uppercase for black moves, lowercase for white moves.
        move_token = notation.upper()[0] + notation[1:] if is_black_turn else notation
        candidate_prefix = history + move_token
        best: str | None = None
        for sequence, name in openings:
            if sequence.startswith(candidate_prefix):
                if best is None or len(sequence) < len(best):
                    best = sequence
                    hints[pos] = name
    return hints


def _opening_book_move(session: GameSession, legal_moves: list[int]) -> int | None:
    history = session.move_record
    matching = [
        (sequence, name)
        for sequence, name in openings
        if len(history) < len(sequence) and sequence.startswith(history)
    ]

    if not matching:
        if not session.opening_book_exhausted:
            session.opening_book_exhausted = True
            session.opening_book_exhausted_at_move = session.move_number + 1
            if session.opening_name_used:
                session.messages.append(
                    f"{session.opponent_name}: Opening book complete ({session.opening_name_used})."
                )
        return None

    candidates: list[tuple[int, str]] = []
    next_index = len(history)
    for sequence, name in matching:
        next_notation = sequence[next_index:next_index + 2]
        if len(next_notation) != 2:
            continue
        next_move = notation_to_position(next_notation)
        if next_move in legal_moves:
            candidates.append((next_move, name))

    if not candidates:
        if not session.opening_book_exhausted:
            session.opening_book_exhausted = True
            session.opening_book_exhausted_at_move = session.move_number + 1
            if session.opening_name_used:
                session.messages.append(
                    f"{session.opponent_name}: Opening book complete ({session.opening_name_used})."
                )
        return None

    chosen_move, chosen_name = random.choice(candidates)
    session.opening_name_used = chosen_name
    return chosen_move


def _resolve_game_outcome(session: GameSession) -> None:
    black_count, white_count, user_count, computer_count = _counts(session.board_state, session.user_color)
    if user_count > computer_count:
        session.winner = "player"
        session.messages.append(f"Congratulations {session.player_name}, you win!")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'lose')}")
    elif computer_count > user_count:
        session.winner = "computer"
        session.messages.append(f"{session.opponent_name} wins!")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'win')}")
    else:
        session.winner = "draw"
        session.messages.append("It's a draw!")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'draw')}")

    _append_final_score(session)
    _write_game_log_if_needed(session)


def _apply_pass(session: GameSession, actor: str) -> None:
    if actor == "player":
        session.messages.append("You have no legal moves and must pass.")
    else:
        session.messages.append(f"{session.opponent_name} has no legal moves and must pass.")

    session.board_state = make_move(None, session.board_state)
    session.consecutive_passes += 1

    if session.consecutive_passes >= 2:
        session.game_over = True
        _resolve_game_outcome(session)


def _register_pass_if_needed(session: GameSession, actor: str) -> bool:
    legal_moves = get_legal_moves(session.board_state)
    if legal_moves:
        return False

    _apply_pass(session, actor)
    return True


def create_new_game(player_name: str, player_color: Player, ai_level: int = 1) -> GameSession:
    if ai_level not in _OPPONENTS_BY_LEVEL:
        raise ValueError("ai_level must be one of: 1, 2, 3, 4, 5, 6")

    computer_color = Player.WHITE if player_color == Player.BLACK else Player.BLACK
    board_state = BoardState(user=player_name)
    opponent = _OPPONENTS_BY_LEVEL[ai_level]

    session = GameSession(
        game_id=board_state.session_id,
        board_state=board_state,
        player_name=player_name,
        user_color=player_color,
        computer_color=computer_color,
        ai_level=ai_level,
        ai_strategy=opponent.strategy,
        ai_parameter=opponent.parameter,
        use_opening_book=opponent.use_opening_book,
        opponent_name=opponent.name,
        opponent_portrait=opponent.portrait,
    )

    session.messages.append(f"Welcome to Othello, {player_name}!")
    color_name = "Black" if player_color == Player.BLACK else "White"
    symbol = "○" if player_color == Player.BLACK else "●"
    session.messages.append(f"You are playing as {color_name} ({symbol}).")
    session.messages.append(
        f"Your opponent is {opponent.name} ({opponent.strategy}: {opponent.parameter})."
    )
    session.messages.append(f"{opponent.name}: {_opponent_phrase(session, 'start')}")

    if player_color == Player.WHITE:
        session.messages.append(f"{opponent.name} goes first...")
        process_computer_move(session)

    return session


def get_state(session: GameSession) -> dict:
    legal_moves = [] if session.game_over else get_legal_moves(session.board_state)
    black_count, white_count, user_count, computer_count = _counts(session.board_state, session.user_color)
    legal_moves_notation = [position_to_notation(move) for move in sorted(legal_moves)]
    opening_hints = _opening_hints_for_moves(session, legal_moves)

    return {
        "game_id": session.game_id,
        "player_name": session.player_name,
        "player_color": session.user_color.value,
        "computer_color": session.computer_color.value,
        "opponent_name": session.opponent_name,
        "opponent_portrait": session.opponent_portrait,
        "ai_level": session.ai_level,
        "ai_strategy": session.ai_strategy,
        "ai_parameter": session.ai_parameter,
        "use_opening_book": session.use_opening_book,
        "opening_book_exhausted": session.opening_book_exhausted,
        "opening_name_used": session.opening_name_used,
        "next_player": session.board_state.next_player.value,
        "board": _board_to_cells(session.board_state),
        "legal_moves": sorted(legal_moves),
        "legal_moves_notation": legal_moves_notation,
        "opening_hints": {str(k): v for k, v in opening_hints.items()},
        "messages": session.messages,
        "move_record": session.move_record,
        "black_count": black_count,
        "white_count": white_count,
        "user_count": user_count,
        "computer_count": computer_count,
        "game_over": session.game_over,
        "winner": session.winner,
        "consecutive_passes": session.consecutive_passes,
        "move_number": session.move_number,
        "last_move": session.last_move,
        "last_player_move": session.last_player_move,
        "last_computer_move": session.last_computer_move,
    }


def process_player_move(session: GameSession, move: int | str) -> dict:
    if session.game_over:
        raise ValueError("Game is already over")
    if session.board_state.next_player != session.user_color:
        raise ValueError("It is not the player's turn")

    parsed_move = notation_to_position(move) if isinstance(move, str) else move
    legal_moves = get_legal_moves(session.board_state)
    if parsed_move not in legal_moves:
        raise ValueError("Illegal move")

    session.board_state = make_move(parsed_move, session.board_state)
    _append_move_record(session, parsed_move, session.user_color)
    session.consecutive_passes = 0
    session.move_number += 1
    notation = position_to_notation(parsed_move)
    session.last_move = {"move": parsed_move, "notation": notation, "actor": "player"}
    session.last_player_move = session.last_move
    session.messages.append(f"{session.player_name} plays {notation}")

    _register_pass_if_needed(session, "computer")
    return get_state(session)


def process_computer_move(session: GameSession, depth: int | None = None) -> dict:
    if session.game_over:
        raise ValueError("Game is already over")
    if session.board_state.next_player != session.computer_color:
        raise ValueError("It is not the computer's turn")

    if _register_pass_if_needed(session, "computer"):
        return get_state(session)

    legal_moves = get_legal_moves(session.board_state)

    move = None
    if session.use_opening_book and not session.opening_book_exhausted:
        move = _opening_book_move(session, legal_moves)

    if move is None and session.ai_strategy == "mcts":
        exploration_budget = session.ai_parameter if depth is None else depth
        move = strategy_mcts.choose_move(session.board_state, exploration_budget)
    elif move is None and session.ai_strategy == "april":
        move = strategy_april.choose_move(session.board_state)
    elif move is None:
        search_depth = session.ai_parameter if depth is None else depth
        move = strategy_negamax.choose_move(session.board_state, search_depth)
    if move is None:
        _register_pass_if_needed(session, "computer")
        return get_state(session)

    session.board_state = make_move(move, session.board_state)
    _append_move_record(session, move, session.computer_color)
    session.consecutive_passes = 0
    session.move_number += 1
    notation = position_to_notation(move)
    session.last_move = {"move": move, "notation": notation, "actor": "computer"}
    session.last_computer_move = session.last_move
    session.messages.append(f"{session.opponent_name} plays {notation}")

    _register_pass_if_needed(session, "player")
    return get_state(session)


def process_pass(session: GameSession, actor: str) -> dict:
    if session.game_over:
        raise ValueError("Game is already over")

    if actor == "player":
        if session.board_state.next_player != session.user_color:
            raise ValueError("It is not the player's turn")
    elif actor == "computer":
        if session.board_state.next_player != session.computer_color:
            raise ValueError("It is not the computer's turn")
    else:
        raise ValueError("actor must be 'player' or 'computer'")

    legal_moves = get_legal_moves(session.board_state)
    if legal_moves:
        raise ValueError("Cannot pass when legal moves are available")

    _apply_pass(session, actor)

    return get_state(session)


def process_resign(session: GameSession, actor: str = "player") -> dict:
    if session.game_over:
        raise ValueError("Game is already over")

    if actor not in {"player", "computer"}:
        raise ValueError("actor must be 'player' or 'computer'")

    session.game_over = True
    if actor == "player":
        session.winner = "computer"
        session.messages.append(f"{session.player_name} resigns. {session.opponent_name} wins.")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'win')}")
    else:
        session.winner = "player"
        session.messages.append(f"{session.opponent_name} resigns. Congratulations {session.player_name}, you win!")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'lose')}")

    _append_final_score(session)
    _write_game_log_if_needed(session)
    return get_state(session)
