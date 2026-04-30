from board_state import BoardState
from directional_scan import flips_for_move
from game_utils import current_and_opponent_pieces


def get_legal_moves(board_state: BoardState) -> list[int]:
    """
    Get all legal moves for the current player in the given board state.
    
    A legal move must:
    1. Be on an empty square
    2. Flip at least one opponent piece by sandwiching it between the new piece
       and an existing piece of the current player's color
    
    Args:
        board_state: The current board state
        
    Returns:
        List of legal move positions (0-63, where 0 is top-left, 63 is bottom-right)
    """
    player_pieces, opponent_pieces = current_and_opponent_pieces(board_state)
    
    # Empty squares are those not occupied by either player
    occupied = player_pieces | opponent_pieces
    empty_squares = ~occupied & ((1 << 64) - 1)
    
    legal_moves = []
    
    # Check each empty square
    for position in range(64):
        if not (empty_squares & (1 << position)):
            continue
            
        # Check if this position is a legal move
        if is_legal_move(position, player_pieces, opponent_pieces):
            legal_moves.append(position)
    
    return legal_moves


def is_legal_move(position: int, player_pieces: int, opponent_pieces: int) -> bool:
    """
    Check if placing a piece at the given position is legal.
    
    Args:
        position: Position to check (0-63)
        player_pieces: Bitmap of current player's pieces
        opponent_pieces: Bitmap of opponent's pieces
        
    Returns:
        True if the move is legal, False otherwise
    """
    return flips_for_move(position, player_pieces, opponent_pieces) != 0
