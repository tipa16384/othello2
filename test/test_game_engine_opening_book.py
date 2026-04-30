import unittest
import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.game_engine import create_new_game, get_state, process_computer_move, process_player_move
from board_state import Player


class TestGameEngineOpeningBook(unittest.TestCase):
    def test_flagged_opponents_have_opening_book_enabled(self):
        donatello = create_new_game("tester", Player.BLACK, ai_level=4)
        shredder = create_new_game("tester", Player.BLACK, ai_level=5)
        self.assertTrue(donatello.use_opening_book)
        self.assertTrue(shredder.use_opening_book)

    def test_opening_book_selects_and_records_opening_name(self):
        session = create_new_game("tester", Player.BLACK, ai_level=4)
        first_move = get_state(session)["legal_moves"][0]
        process_player_move(session, first_move)

        after_computer = process_computer_move(session)
        self.assertIsNotNone(session.opening_name_used)
        self.assertFalse(session.opening_book_exhausted)
        self.assertRegex(after_computer["move_record"], r"^[A-H][1-8][a-h][1-8]$")

    def test_exhaustion_marks_session_and_mentions_last_used_opening(self):
        session = create_new_game("tester", Player.BLACK, ai_level=4)
        first_move = get_state(session)["legal_moves"][0]
        process_player_move(session, first_move)
        process_computer_move(session)

        used_opening = session.opening_name_used
        self.assertIsNotNone(used_opening)

        # Force a no-match history and computer turn to trigger one-time exhaustion transition.
        session.move_record = "A1"
        session.board_state.next_player = session.computer_color

        process_computer_move(session)
        self.assertTrue(session.opening_book_exhausted)
        self.assertTrue(
            any(
                "Opening book complete" in msg and used_opening in msg
                for msg in session.messages
            )
        )


if __name__ == "__main__":
    unittest.main()
