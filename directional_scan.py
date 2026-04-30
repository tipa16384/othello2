from game_utils import DIRECTIONS


def flips_for_move(position: int, player_pieces: int, opponent_pieces: int) -> int:
    """Return a bitmask of opponent pieces that would be flipped by this move."""
    row = position // 8
    col = position % 8

    flips = 0
    for dr, dc in DIRECTIONS:
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
    path_mask = 0

    while 0 <= r < 8 and 0 <= c < 8:
        pos = r * 8 + c
        pos_mask = 1 << pos

        if opponent_pieces & pos_mask:
            path_mask |= pos_mask
            r += dr
            c += dc
            continue

        if player_pieces & pos_mask:
            return path_mask

        return 0

    return 0
