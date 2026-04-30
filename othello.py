from board_state import BoardState, Player
from game_utils import notation_to_position, position_to_notation
from legal_moves import get_legal_moves
from make_move import make_move
from display_board import display_board
import strategy_negamax
import strategy_mcts

def main():
    """Main game loop for Othello."""
    print("Welcome to Othello!")
    user_name = input("Enter your name: ").strip()
    
    # Let user choose color
    while True:
        color_choice = input("\nChoose your color - (B)lack or (W)hite? ").strip().upper()
        if color_choice in ['B', 'BLACK']:
            user_color = Player.BLACK
            computer_color = Player.WHITE
            user_symbol = "○"
            break
        elif color_choice in ['W', 'WHITE']:
            user_color = Player.WHITE
            computer_color = Player.BLACK
            user_symbol = "●"
            break
        else:
            print("Please enter 'B' for Black or 'W' for White.")
    
    # Initialize game
    board_state = BoardState(user=user_name)
    consecutive_passes = 0
    
    color_name = "Black" if user_color == Player.BLACK else "White"
    print(f"\n{user_name}, you are playing as {color_name} ({user_symbol})")
    print("Starting position:")
    display_board(board_state)
    print()
    
    # If user chose white, computer (black) goes first
    if user_color == Player.WHITE:
        print("Computer goes first...")
        legal_moves = get_legal_moves(board_state)
        move = strategy_negamax.choose_move(board_state, 6)
        move_notation = position_to_notation(move)
        print(f"Computer plays {move_notation}")
        board_state = make_move(move, board_state)
        print()
    
    # Game loop
    while consecutive_passes < 2:
        legal_moves = get_legal_moves(board_state)
        
        if not legal_moves:
            # Current player must pass
            player_name = "You have" if board_state.next_player == user_color else "Computer has"
            print(f"{player_name} no legal moves and must pass.")
            board_state = make_move(None, board_state)
            consecutive_passes += 1
            print()
            continue
        
        # Reset pass count on successful move
        consecutive_passes = 0

        if board_state.next_player == computer_color:
            # Computer's turn
            move = strategy_negamax.choose_move(board_state, 6)
            move_notation = position_to_notation(move)
            print(f"Computer plays {move_notation}")
            board_state = make_move(move, board_state)
            # display_board(board_state)
            print()
        else:
            # Human player's turn
            display_board(board_state)
            print(f"Your legal moves: {_format_legal_moves(legal_moves)}")
            
            # Get valid move from user
            while True:
                move_input = input("Enter your move: ").strip().lower()
                try:
                    move = notation_to_position(move_input)
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
    
    black_count = board_state.black.bit_count()
    white_count = board_state.white.bit_count()
    
    user_count = black_count if user_color == Player.BLACK else white_count
    computer_count = white_count if user_color == Player.BLACK else black_count
    user_color_name = "Black" if user_color == Player.BLACK else "White"
    computer_color_name = "White" if user_color == Player.BLACK else "Black"
    
    print(f"\n{user_color_name} (You): {user_count}")
    print(f"{computer_color_name} (Computer): {computer_count}")
    
    if user_count > computer_count:
        print(f"\nCongratulations {user_name}, you win!")
    elif computer_count > user_count:
        print("\nComputer wins!")
    else:
        print("\nIt's a draw!")


def _format_legal_moves(legal_moves: list[int]) -> str:
    """Format list of legal moves as readable string."""
    notations = [position_to_notation(move) for move in legal_moves]
    return ", ".join(sorted(notations))


if __name__ == "__main__":
    main()
