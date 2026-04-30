from board_state import BoardState, Player
from directional_scan import flips_for_move
from game_utils import current_and_opponent_pieces, toggle_player
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
            next_player=toggle_player(board_state.next_player),
            session_id=board_state.session_id,
        )

    if not isinstance(move, int) or move < 0 or move > 63:
        raise ValueError("move must be an integer in the range 0-63")

    legal_moves = get_legal_moves(board_state)
    if move not in legal_moves:
        raise ValueError("illegal move")

    player_pieces, opponent_pieces = current_and_opponent_pieces(board_state)
    player_is_black = board_state.next_player == Player.BLACK

    flips_mask = flips_for_move(move, player_pieces, opponent_pieces)
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
        next_player=toggle_player(board_state.next_player),
        session_id=board_state.session_id,
    )
