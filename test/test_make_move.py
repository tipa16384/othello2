import unittest
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from board_state import BoardState, Player
from make_move import make_move
from legal_moves import get_legal_moves


class TestMakeMove(unittest.TestCase):

    def test_pass_move_toggles_player(self):
        """Passing (move=None) should toggle the next player without changing pieces."""
        board = BoardState(user="testuser")
        new_board = make_move(None, board)

        self.assertEqual(new_board.black, board.black)
        self.assertEqual(new_board.white, board.white)
        self.assertEqual(new_board.next_player, Player.WHITE)
        self.assertEqual(new_board.user, board.user)
        self.assertEqual(new_board.session_id, board.session_id)

    def test_illegal_move_raises(self):
        """An illegal move should raise ValueError."""
        board = BoardState(user="testuser")
        with self.assertRaises(ValueError):
            make_move(0, board)  # corner is illegal from starting position

    def test_out_of_bounds_raises(self):
        """Out of bounds move should raise ValueError."""
        board = BoardState(user="testuser")
        with self.assertRaises(ValueError):
            make_move(-1, board)
        with self.assertRaises(ValueError):
            make_move(64, board)

    def test_valid_move_flips_pieces(self):
        """A valid move should flip the appropriate opponent pieces."""
        board = BoardState(user="testuser")

        # From starting position, black can move to position 19 (d3)
        new_board = make_move(19, board)

        # Black should now include the new move and the flipped piece at 27 (d4)
        self.assertTrue(new_board.black & (1 << 19))
        self.assertTrue(new_board.black & (1 << 27))

        # White should have lost the piece at 27
        self.assertFalse(new_board.white & (1 << 27))

        # Next player should be white
        self.assertEqual(new_board.next_player, Player.WHITE)

    def test_valid_move_returns_new_state(self):
        """make_move should return a new BoardState without mutating the original."""
        board = BoardState(user="testuser")
        original_black = board.black
        original_white = board.white

        move = get_legal_moves(board)[0]
        new_board = make_move(move, board)

        self.assertIsNot(new_board, board)
        self.assertEqual(board.black, original_black)
        self.assertEqual(board.white, original_white)

    def test_white_move_flips_pieces(self):
        """Test a legal move for white and verify flipping."""
        board = BoardState(user="testuser", next_player=Player.WHITE)

        # From starting position, white can move to position 20 (e3)
        new_board = make_move(20, board)

        # White should now include the new move and the flipped piece at 28 (e4)
        self.assertTrue(new_board.white & (1 << 20))
        self.assertTrue(new_board.white & (1 << 28))

        # Black should have lost the piece at 28
        self.assertFalse(new_board.black & (1 << 28))

        # Next player should be black
        self.assertEqual(new_board.next_player, Player.BLACK)

    def test_session_id_preserved(self):
        """Session ID should be preserved across moves."""
        board = BoardState(user="testuser")
        move = get_legal_moves(board)[0]
        new_board = make_move(move, board)

        self.assertEqual(new_board.session_id, board.session_id)


if __name__ == "__main__":
    unittest.main()
