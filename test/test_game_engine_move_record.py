import unittest
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.game_engine import create_new_game, get_state, process_computer_move, process_player_move
from board_state import Player


class TestGameEngineMoveRecord(unittest.TestCase):
    def test_starts_empty(self):
        session = create_new_game("tester", Player.BLACK, ai_level=1)
        state = get_state(session)
        self.assertEqual(state["move_record"], "")

    def test_black_then_white_casing(self):
        session = create_new_game("tester", Player.BLACK, ai_level=1)
        initial = get_state(session)
        first_move = initial["legal_moves"][0]

        after_player = process_player_move(session, first_move)
        self.assertRegex(after_player["move_record"], r"^[A-H][1-8]$")

        after_computer = process_computer_move(session)
        self.assertRegex(after_computer["move_record"], r"^[A-H][1-8][a-h][1-8]$")

    def test_white_opening_includes_black_first(self):
        session = create_new_game("tester", Player.WHITE, ai_level=1)
        state = get_state(session)
        self.assertRegex(state["move_record"], r"^[A-H][1-8]$")


if __name__ == "__main__":
    unittest.main()
