from __future__ import annotations

from board_state import BoardState, Player


# 8 directions: N, NE, E, SE, S, SW, W, NW
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (-1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, -1),
)


# Tuple format: (name, portrait, strategy, parameter, use_opening_book)
OPPONENT_PROFILES: list[tuple[str, str, str, int, bool]] = [
    ("Michelangelo", "/web/portraits/michelangelo.svg", "negamax", 3, False),
    ("Raphael", "/web/portraits/raphael.svg", "negamax", 4, False),
    ("Leonardo", "/web/portraits/leonardo.svg", "negamax", 5, False),
    ("Donatello", "/web/portraits/donatello.svg", "negamax", 6, True),
    ("Shredder", "/web/portraits/shredder.svg", "mcts", 10000, True),
    ("April", "/web/portraits/april.svg", "april", 1, False),
]


def toggle_player(player: Player) -> Player:
    return Player.WHITE if player == Player.BLACK else Player.BLACK


def current_and_opponent_pieces(board_state: BoardState) -> tuple[int, int]:
    if board_state.next_player == Player.BLACK:
        return board_state.black, board_state.white
    return board_state.white, board_state.black


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


def counts_for_user(board_state: BoardState, user_color: Player) -> tuple[int, int, int, int]:
    black_count = board_state.black.bit_count()
    white_count = board_state.white.bit_count()
    user_count = black_count if user_color == Player.BLACK else white_count
    computer_count = white_count if user_color == Player.BLACK else black_count
    return black_count, white_count, user_count, computer_count
