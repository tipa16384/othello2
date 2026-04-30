import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.game_engine import _write_game_log_if_needed, create_new_game, process_resign
from board_state import Player


class TestGameLogs(unittest.TestCase):
    def test_finished_game_writes_timestamped_json_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_value = os.environ.get("OTHELLO_GAMELOG_DIR")
            os.environ["OTHELLO_GAMELOG_DIR"] = tmp
            try:
                session = create_new_game("tester", Player.BLACK, ai_level=1)
                process_resign(session, "player")

                files = list(Path(tmp).glob("*.json"))
                self.assertEqual(len(files), 1)
                self.assertRegex(
                    files[0].name,
                    r"^\d{8}_\d{6}_\d{6}_[0-9a-f\-]+\.json$",
                )

                payload = json.loads(files[0].read_text(encoding="utf-8"))
                self.assertEqual(payload["game_id"], session.game_id)
                self.assertEqual(payload["winner"], "computer")
                self.assertEqual(payload["player_name"], "tester")
                self.assertEqual(payload["black_player"], 'Player "tester"')
                self.assertEqual(payload["white_player"], "Negamax depth 3 (Michelangelo)")
                self.assertIn("windows", payload)
            finally:
                if old_value is None:
                    os.environ.pop("OTHELLO_GAMELOG_DIR", None)
                else:
                    os.environ["OTHELLO_GAMELOG_DIR"] = old_value

    def test_white_side_participant_labels_are_reversed(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_value = os.environ.get("OTHELLO_GAMELOG_DIR")
            os.environ["OTHELLO_GAMELOG_DIR"] = tmp
            try:
                session = create_new_game("tester", Player.WHITE, ai_level=5)
                process_resign(session, "player")

                files = list(Path(tmp).glob("*.json"))
                self.assertEqual(len(files), 1)

                payload = json.loads(files[0].read_text(encoding="utf-8"))
                self.assertEqual(payload["black_player"], "MCTS 10000 (Shredder)")
                self.assertEqual(payload["white_player"], 'Player "tester"')
            finally:
                if old_value is None:
                    os.environ.pop("OTHELLO_GAMELOG_DIR", None)
                else:
                    os.environ["OTHELLO_GAMELOG_DIR"] = old_value

    def test_finished_game_is_logged_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_value = os.environ.get("OTHELLO_GAMELOG_DIR")
            os.environ["OTHELLO_GAMELOG_DIR"] = tmp
            try:
                session = create_new_game("tester", Player.BLACK, ai_level=1)
                process_resign(session, "player")
                first_path = session.game_log_path

                files = list(Path(tmp).glob("*.json"))
                self.assertEqual(len(files), 1)

                # Simulate a second finish-path attempt; guard should prevent a duplicate file.
                _write_game_log_if_needed(session)

                files_after = list(Path(tmp).glob("*.json"))
                self.assertEqual(len(files_after), 1)
                self.assertEqual(session.game_log_path, first_path)
            finally:
                if old_value is None:
                    os.environ.pop("OTHELLO_GAMELOG_DIR", None)
                else:
                    os.environ["OTHELLO_GAMELOG_DIR"] = old_value


if __name__ == "__main__":
    unittest.main()
