import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from board_state import BoardState, Player
from legal_moves import get_legal_moves
from strategy_april import choose_move


class TestStrategyApril(unittest.TestCase):
    def test_returns_none_when_no_moves(self):
        board = BoardState(
            user="testuser",
            black=0,
            white=0,
            next_player=Player.BLACK,
        )
        self.assertIsNone(choose_move(board))

    def test_returns_legal_move(self):
        board = BoardState(user="testuser")
        legal_moves = get_legal_moves(board)
        move = choose_move(board)
        self.assertIn(move, legal_moves)

    def test_deterministic_tie_break_with_seed(self):
        board = BoardState(user="testuser")
        random.seed(1234)
        move1 = choose_move(board)
        random.seed(1234)
        move2 = choose_move(board)
        self.assertEqual(move1, move2)


if __name__ == "__main__":
    unittest.main()
