from board_state import BoardState


def display_board(board_state: BoardState) -> None:
    """
    Display the Othello board in the console with column letters and row numbers.
    """
    header = "  A B C D E F G H"
    print(header)

    for row in range(8):
        row_cells = []
        for col in range(8):
            pos = row * 8 + col
            mask = 1 << pos
            if board_state.black & mask:
                cell = "○"
            elif board_state.white & mask:
                cell = "●"
            else:
                cell = "·"
            row_cells.append(cell)

        row_number = str(row + 1)
        print(f"{row_number} " + " ".join(row_cells) + f" {row_number}")

    print(header)
