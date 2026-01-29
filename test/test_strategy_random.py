import unittest
import sys
from pathlib import Path
import random

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from strategy_random import choose_move


class TestStrategyRandom(unittest.TestCase):

    def test_returns_none_when_no_moves(self):
        """Should return None if there are no legal moves."""
        board = BoardState(
            user="testuser",
            black=0,
            white=0,
            next_player=Player.BLACK,
        )
        move = choose_move(board)
        self.assertIsNone(move)

    def test_returns_legal_move(self):
        """Should return a move that is legal for the current player."""
        board = BoardState(user="testuser")
        legal_moves = get_legal_moves(board)

        move = choose_move(board)
        self.assertIn(move, legal_moves)

    def test_random_choice_is_deterministic_with_seed(self):
        """With a fixed seed, the chosen move should be reproducible."""
        board = BoardState(user="testuser")
        legal_moves = get_legal_moves(board)

        random.seed(12345)
        move1 = choose_move(board)

        random.seed(12345)
        move2 = choose_move(board)

        self.assertIn(move1, legal_moves)
        self.assertEqual(move1, move2)


if __name__ == "__main__":
    unittest.main()
