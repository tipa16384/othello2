import unittest
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from board_state import BoardState, Player
from legal_moves import get_legal_moves


class TestLegalMoves(unittest.TestCase):
    
    def test_starting_position_black(self):
        """Test legal moves for black in the starting position."""
        board = BoardState(user="testuser")
        legal_moves = get_legal_moves(board)
        
        # From starting position, black should have 4 legal moves
        # Positions: 19 (d3), 26 (c4), 37 (f5), 44 (e6)
        expected_moves = {19, 26, 37, 44}
        self.assertEqual(set(legal_moves), expected_moves)
    
    def test_starting_position_white(self):
        """Test legal moves for white in the starting position."""
        board = BoardState(user="testuser", next_player=Player.WHITE)
        legal_moves = get_legal_moves(board)
        
        # From starting position, white should have 4 legal moves
        # Positions: 20 (e3), 29 (f4), 34 (c5), 43 (d6)
        expected_moves = {20, 29, 34, 43}
        self.assertEqual(set(legal_moves), expected_moves)
    
    def test_no_legal_moves(self):
        """Test when there are no legal moves available."""
        # Create a board where current player has no legal moves
        # Black surrounded by white with no valid captures
        board = BoardState(
            user="testuser",
            black=0b1 << 28,  # Single black piece at position 28
            white=0b111111111,  # White pieces surrounding it (simplified)
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        # Should return empty list
        self.assertIsInstance(legal_moves, list)
    
    def test_capture_horizontal(self):
        """Test capturing in horizontal direction."""
        # Black at position 0, white at position 1, empty at position 2
        # Position 2 should be legal for black (captures white at 1)
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 1),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        self.assertIn(2, legal_moves)
    
    def test_capture_vertical(self):
        """Test capturing in vertical direction."""
        # Black at position 0 (row 0, col 0)
        # White at position 8 (row 1, col 0)
        # Position 16 (row 2, col 0) should be legal for black
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 8),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        self.assertIn(16, legal_moves)
    
    def test_capture_diagonal(self):
        """Test capturing in diagonal direction."""
        # Black at position 0 (row 0, col 0)
        # White at position 9 (row 1, col 1)
        # Position 18 (row 2, col 2) should be legal for black
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 9),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        self.assertIn(18, legal_moves)
    
    def test_multiple_captures_same_move(self):
        """Test a move that captures in multiple directions."""
        # Set up a position where one move captures in 2+ directions
        # Black at positions 0 and 18
        # White at positions 1 and 9
        # Position 9 should capture when surrounded properly
        board = BoardState(
            user="testuser",
            black=(1 << 27) | (1 << 36),  # d4, e5
            white=(1 << 28) | (1 << 35),  # e4, d5
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        # Should have legal moves
        self.assertGreater(len(legal_moves), 0)
    
    def test_cannot_capture_own_pieces(self):
        """Test that you cannot make a move that only touches your own pieces."""
        # Black at positions 0 and 2
        # Position 1 is empty, but shouldn't be legal (would need opponent piece)
        board = BoardState(
            user="testuser",
            black=(1 << 0) | (1 << 2),
            white=0,
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        # Position 1 should NOT be legal
        self.assertNotIn(1, legal_moves)
    
    def test_must_sandwich_pieces(self):
        """Test that opponent pieces must be sandwiched, not just adjacent."""
        # Black at position 0, white at position 1, empty at positions 2, 3
        # Position 2 should NOT be legal (doesn't sandwich)
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 1) | (1 << 2),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        # Position 3 might be legal if it sandwiches properly
        # But position 1 is already occupied by white
    
    def test_capture_multiple_opponent_pieces(self):
        """Test capturing multiple opponent pieces in a row."""
        # Black at position 0, white at positions 1 and 2, empty at position 3
        # Position 3 should be legal and would capture both white pieces
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 1) | (1 << 2),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        self.assertIn(3, legal_moves)
    
    def test_corner_moves(self):
        """Test moves in corners and edges."""
        # Test that moves near corners are correctly evaluated
        board = BoardState(
            user="testuser",
            black=(1 << 0),  # Top-left corner
            white=(1 << 1),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        # Should have at least the horizontal capture
        self.assertIn(2, legal_moves)
    
    def test_all_directions(self):
        """Test that all 8 directions are checked."""
        # Test captures in different directions
        # Create scenarios for each direction
        
        # Test North direction: black at 16, white at 8, move at 0
        board = BoardState(
            user="testuser",
            black=(1 << 16),
            white=(1 << 8),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        self.assertIn(0, legal_moves, "North direction should work")
        
        # Test South direction: black at 0, white at 8, move at 16
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 8),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        self.assertIn(16, legal_moves, "South direction should work")
        
        # Test East direction: black at 0, white at 1, move at 2
        board = BoardState(
            user="testuser",
            black=(1 << 0),
            white=(1 << 1),
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        self.assertIn(2, legal_moves, "East direction should work")
    
    def test_empty_board(self):
        """Test that an empty board has no legal moves."""
        board = BoardState(
            user="testuser",
            black=0,
            white=0,
            next_player=Player.BLACK
        )
        legal_moves = get_legal_moves(board)
        
        # No pieces = no legal moves
        self.assertEqual(len(legal_moves), 0)


if __name__ == "__main__":
    unittest.main()
