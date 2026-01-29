from board_state import BoardState, Player
from legal_moves import get_legal_moves


def make_move(move: int | None, board_state: BoardState) -> BoardState:
    """
    Apply a move to the board and return a new BoardState.

    Args:
        move: Position 0-63, or None to pass (no legal moves)
        board_state: Current board state

    Returns:
        New BoardState after applying the move

    Raises:
        ValueError: If move is illegal or out of bounds
    """
    if move is None:
        return BoardState(
            user=board_state.user,
            black=board_state.black,
            white=board_state.white,
            next_player=_toggle_player(board_state.next_player),
            session_id=board_state.session_id,
        )

    if not isinstance(move, int) or move < 0 or move > 63:
        raise ValueError("move must be an integer in the range 0-63")

    legal_moves = get_legal_moves(board_state)
    if move not in legal_moves:
        raise ValueError("illegal move")

    if board_state.next_player == Player.BLACK:
        player_pieces = board_state.black
        opponent_pieces = board_state.white
        player_is_black = True
    else:
        player_pieces = board_state.white
        opponent_pieces = board_state.black
        player_is_black = False

    flips_mask = _get_flips_mask(move, player_pieces, opponent_pieces)
    move_mask = 1 << move

    new_player_pieces = player_pieces | flips_mask | move_mask
    new_opponent_pieces = opponent_pieces & ~flips_mask

    if player_is_black:
        new_black = new_player_pieces
        new_white = new_opponent_pieces
    else:
        new_white = new_player_pieces
        new_black = new_opponent_pieces

    return BoardState(
        user=board_state.user,
        black=new_black,
        white=new_white,
        next_player=_toggle_player(board_state.next_player),
        session_id=board_state.session_id,
    )


def _toggle_player(player: Player) -> Player:
    return Player.WHITE if player == Player.BLACK else Player.BLACK


def _get_flips_mask(position: int, player_pieces: int, opponent_pieces: int) -> int:
    row = position // 8
    col = position % 8

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

    flips = 0
    for dr, dc in directions:
        flips |= _flips_in_direction(row, col, dr, dc, player_pieces, opponent_pieces)

    return flips


def _flips_in_direction(
    row: int,
    col: int,
    dr: int,
    dc: int,
    player_pieces: int,
    opponent_pieces: int,
) -> int:
    r, c = row + dr, col + dc
    path = []

    while 0 <= r < 8 and 0 <= c < 8:
        pos = r * 8 + c
        pos_mask = 1 << pos

        if opponent_pieces & pos_mask:
            path.append(pos)
            r += dr
            c += dc
            continue

        if player_pieces & pos_mask:
            if path:
                flips = 0
                for p in path:
                    flips |= 1 << p
                return flips
            return 0

        return 0

    return 0
