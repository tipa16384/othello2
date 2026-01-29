from board_state import BoardState, Player
from legal_moves import get_legal_moves
from make_move import make_move
from display_board import display_board
from strategy_negamax import choose_move


def main():
    """Main game loop for Othello."""
    print("Welcome to Othello!")
    user_name = input("Enter your name: ").strip()
    
    # Initialize game - player is black, computer is white
    board_state = BoardState(user=user_name)
    consecutive_passes = 0
    
    print(f"\n{user_name}, you are playing as Black (●)")
    print("Starting position:")
    display_board(board_state)
    print()
    
    # Game loop
    while consecutive_passes < 2:
        legal_moves = get_legal_moves(board_state)
        
        if not legal_moves:
            # Current player must pass
            player_name = "You have" if board_state.next_player == Player.BLACK else "Computer has"
            print(f"{player_name} no legal moves and must pass.")
            board_state = make_move(None, board_state)
            consecutive_passes += 1
            print()
            continue
        
        # Reset pass count on successful move
        consecutive_passes = 0
        
        if board_state.next_player == Player.WHITE:
            # Computer's turn
            move = choose_move(board_state)
            move_notation = _position_to_notation(move)
            print(f"Computer plays {move_notation}")
            board_state = make_move(move, board_state)
            display_board(board_state)
            print()
        else:
            # Human player's turn
            display_board(board_state)
            print(f"Your legal moves: {_format_legal_moves(legal_moves)}")
            
            # Get valid move from user
            while True:
                move_input = input("Enter your move: ").strip().lower()
                try:
                    move = _notation_to_position(move_input)
                    if move in legal_moves:
                        break
                    else:
                        print(f"Invalid move. Please choose from: {_format_legal_moves(legal_moves)}")
                except ValueError:
                    print(f"Invalid format. Please use format like 'd3'. Valid moves: {_format_legal_moves(legal_moves)}")
            
            board_state = make_move(move, board_state)
            print()
    
    # Game over - count pieces
    print("Game Over!")
    print("\nFinal board:")
    display_board(board_state)
    
    black_count = bin(board_state.black).count('1')
    white_count = bin(board_state.white).count('1')
    
    print(f"\nBlack (You): {black_count}")
    print(f"White (Computer): {white_count}")
    
    if black_count > white_count:
        print(f"\nCongratulations {user_name}, you win!")
    elif white_count > black_count:
        print("\nComputer wins!")
    else:
        print("\nIt's a draw!")


def _position_to_notation(position: int) -> str:
    """Convert position (0-63) to chess-like notation (e.g., 'd3')."""
    row = position // 8
    col = position % 8
    return f"{chr(ord('a') + col)}{row + 1}"


def _notation_to_position(notation: str) -> int:
    """Convert chess-like notation (e.g., 'd3') to position (0-63)."""
    if len(notation) != 2:
        raise ValueError("Invalid notation format")
    
    col = ord(notation[0]) - ord('a')
    row = int(notation[1]) - 1
    
    if not (0 <= col < 8 and 0 <= row < 8):
        raise ValueError("Position out of bounds")
    
    return row * 8 + col


def _format_legal_moves(legal_moves: list[int]) -> str:
    """Format list of legal moves as readable string."""
    notations = [_position_to_notation(move) for move in legal_moves]
    return ", ".join(sorted(notations))


if __name__ == "__main__":
    main()
