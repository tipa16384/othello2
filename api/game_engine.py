from __future__ import annotations

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move
import strategy_negamax

from api.game_session import GameSession


OPPONENTS_BY_DEPTH: dict[int, dict[str, str]] = {
    3: {
        "name": "Michelangelo",
        "portrait": "/web/portraits/michelangelo.svg",
        "start": "Let's go, dudes!",
        "win": "Booyakasha! I win!",
        "lose": "Aw man... pizza break?",
        "draw": "Tie? Still fun!",
    },
    4: {
        "name": "Raphael",
        "portrait": "/web/portraits/raphael.svg",
        "start": "Alright, let's do this.",
        "win": "Yeah! That's how it's done.",
        "lose": "Tch. Lucky.",
        "draw": "Whatever. Call it even.",
    },
    5: {
        "name": "Leonardo",
        "portrait": "/web/portraits/leonardo.svg",
        "start": "Focus. Begin.",
        "win": "Victory is mine.",
        "lose": "I need more practice.",
        "draw": "A balanced match.",
    },
    6: {
        "name": "Donatello",
        "portrait": "/web/portraits/donatello.svg",
        "start": "Analyzing board... go.",
        "win": "Optimal play confirmed.",
        "lose": "Unexpected outcome.",
        "draw": "Statistically equal.",
    },
}


def _opponent_phrase(session: GameSession, key: str) -> str:
    for profile in OPPONENTS_BY_DEPTH.values():
        if profile["name"] == session.opponent_name:
            return profile[key]
    return ""


def position_to_notation(position: int) -> str:
    row = position // 8
    col = position % 8
    return f"{chr(ord('a') + col)}{row + 1}"


def notation_to_position(notation: str) -> int:
    cleaned = notation.strip().lower()
    if len(cleaned) != 2:
        raise ValueError("Invalid notation format")

    col = ord(cleaned[0]) - ord("a")
    row = int(cleaned[1]) - 1
    if not (0 <= col < 8 and 0 <= row < 8):
        raise ValueError("Position out of bounds")

    return row * 8 + col


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
    black_count = board_state.black.bit_count()
    white_count = board_state.white.bit_count()
    user_count = black_count if user_color == Player.BLACK else white_count
    computer_count = white_count if user_color == Player.BLACK else black_count
    return black_count, white_count, user_count, computer_count


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

    session.messages.append(f"Final score - Black: {black_count}, White: {white_count}")


def _register_pass_if_needed(session: GameSession, actor: str) -> bool:
    legal_moves = get_legal_moves(session.board_state)
    if legal_moves:
        return False

    if actor == "player":
        session.messages.append("You have no legal moves and must pass.")
    else:
        session.messages.append(f"{session.opponent_name} has no legal moves and must pass.")

    session.board_state = make_move(None, session.board_state)
    session.consecutive_passes += 1

    if session.consecutive_passes >= 2:
        session.game_over = True
        _resolve_game_outcome(session)
    return True


def create_new_game(player_name: str, player_color: Player, ai_depth: int = 3) -> GameSession:
    if ai_depth not in OPPONENTS_BY_DEPTH:
        raise ValueError("ai_depth must be one of: 3, 4, 5, 6")

    computer_color = Player.WHITE if player_color == Player.BLACK else Player.BLACK
    board_state = BoardState(user=player_name)
    opponent_profile = OPPONENTS_BY_DEPTH[ai_depth]
    opponent_name = opponent_profile["name"]
    opponent_portrait = opponent_profile["portrait"]

    session = GameSession(
        game_id=board_state.session_id,
        board_state=board_state,
        player_name=player_name,
        user_color=player_color,
        computer_color=computer_color,
        ai_depth=ai_depth,
        opponent_name=opponent_name,
        opponent_portrait=opponent_portrait,
    )

    session.messages.append(f"Welcome to Othello, {player_name}!")
    color_name = "Black" if player_color == Player.BLACK else "White"
    symbol = "○" if player_color == Player.BLACK else "●"
    session.messages.append(f"You are playing as {color_name} ({symbol}).")
    session.messages.append(f"Your opponent is {opponent_name} (depth {ai_depth}).")
    session.messages.append(f"{opponent_name}: {_opponent_phrase(session, 'start')}")

    if player_color == Player.WHITE:
        session.messages.append(f"{opponent_name} goes first...")
        process_computer_move(session)

    return session


def get_state(session: GameSession) -> dict:
    legal_moves = [] if session.game_over else get_legal_moves(session.board_state)
    black_count, white_count, user_count, computer_count = _counts(session.board_state, session.user_color)
    legal_moves_notation = [position_to_notation(move) for move in sorted(legal_moves)]

    return {
        "game_id": session.game_id,
        "player_name": session.player_name,
        "player_color": session.user_color.value,
        "computer_color": session.computer_color.value,
        "opponent_name": session.opponent_name,
        "opponent_portrait": session.opponent_portrait,
        "ai_depth": session.ai_depth,
        "next_player": session.board_state.next_player.value,
        "board": _board_to_cells(session.board_state),
        "legal_moves": sorted(legal_moves),
        "legal_moves_notation": legal_moves_notation,
        "messages": session.messages,
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

    search_depth = session.ai_depth if depth is None else depth
    move = strategy_negamax.choose_move(session.board_state, search_depth)
    if move is None:
        _register_pass_if_needed(session, "computer")
        return get_state(session)

    session.board_state = make_move(move, session.board_state)
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

    session.board_state = make_move(None, session.board_state)
    session.consecutive_passes += 1

    if actor == "player":
        session.messages.append("You have no legal moves and must pass.")
    else:
        session.messages.append(f"{session.opponent_name} has no legal moves and must pass.")

    if session.consecutive_passes >= 2:
        session.game_over = True
        _resolve_game_outcome(session)

    return get_state(session)


def process_resign(session: GameSession, actor: str = "player") -> dict:
    if session.game_over:
        raise ValueError("Game is already over")

    if actor not in {"player", "computer"}:
        raise ValueError("actor must be 'player' or 'computer'")

    session.game_over = True
    black_count, white_count, _, _ = _counts(session.board_state, session.user_color)

    if actor == "player":
        session.winner = "computer"
        session.messages.append(f"{session.player_name} resigns. {session.opponent_name} wins.")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'win')}")
    else:
        session.winner = "player"
        session.messages.append(f"{session.opponent_name} resigns. Congratulations {session.player_name}, you win!")
        session.messages.append(f"{session.opponent_name}: {_opponent_phrase(session, 'lose')}")

    session.messages.append(f"Final score - Black: {black_count}, White: {white_count}")
    return get_state(session)
