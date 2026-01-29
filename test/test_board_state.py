import unittest
import sys
import uuid
from pathlib import Path

# Add parent directory to path to import board_state
sys.path.insert(0, str(Path(__file__).parent.parent))

from board_state import BoardState, Player


class TestBoardState(unittest.TestCase):
    
    def test_minimal_initialization(self):
        """Test creating a BoardState with only the required user parameter."""
        board = BoardState(user="testuser")
        
        self.assertEqual(board.user, "testuser")
        self.assertEqual(board.black, BoardState.DEFAULT_BLACK)
        self.assertEqual(board.white, BoardState.DEFAULT_WHITE)
        self.assertEqual(board.next_player, Player.BLACK)
        self.assertIsNotNone(board.session_id)
        # Verify it's a valid UUID format
        uuid.UUID(board.session_id)
    
    def test_default_starting_position(self):
        """Test that default black and white positions are correct."""
        board = BoardState(user="testuser")
        
        # Starting position: black at positions 28 and 35
        expected_black = (1 << 28) | (1 << 35)
        self.assertEqual(board.black, expected_black)
        
        # Starting position: white at positions 27 and 36
        expected_white = (1 << 27) | (1 << 36)
        self.assertEqual(board.white, expected_white)
    
    def test_custom_values(self):
        """Test creating a BoardState with custom values."""
        custom_black = 0xFF
        custom_white = 0xF0
        custom_session_id = str(uuid.uuid4())
        
        board = BoardState(
            user="customuser",
            black=custom_black,
            white=custom_white,
            next_player=Player.WHITE,
            session_id=custom_session_id
        )
        
        self.assertEqual(board.user, "customuser")
        self.assertEqual(board.black, custom_black)
        self.assertEqual(board.white, custom_white)
        self.assertEqual(board.next_player, Player.WHITE)
        self.assertEqual(board.session_id, custom_session_id)
    
    def test_next_player_default(self):
        """Test that the default next_player is BLACK."""
        board = BoardState(user="testuser")
        self.assertEqual(board.next_player, Player.BLACK)
    
    def test_session_id_uniqueness(self):
        """Test that each BoardState gets a unique session_id by default."""
        board1 = BoardState(user="user1")
        board2 = BoardState(user="user2")
        
        self.assertNotEqual(board1.session_id, board2.session_id)
    
    def test_player_enum_values(self):
        """Test Player enum has correct values."""
        self.assertEqual(Player.BLACK.value, "black")
        self.assertEqual(Player.WHITE.value, "white")
    
    def test_64bit_integers(self):
        """Test that black and white can hold 64-bit values."""
        max_64bit = (1 << 64) - 1
        
        board = BoardState(
            user="testuser",
            black=max_64bit,
            white=max_64bit
        )
        
        self.assertEqual(board.black, max_64bit)
        self.assertEqual(board.white, max_64bit)


if __name__ == "__main__":
    unittest.main()
