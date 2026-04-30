import random
import json
import re
import tempfile
import unittest
from pathlib import Path

import httpx
from live_server import LiveServer

try:
    from websockets.sync.client import connect as ws_connect
except ModuleNotFoundError:
    ws_connect = None


ROOT = Path(__file__).resolve().parent.parent


@unittest.skipIf(ws_connect is None, "websockets dependency is not installed")
class TestLiveFastApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.log_dir = tempfile.TemporaryDirectory()
        cls.server = LiveServer(
            startup_timeout=20,
            health_timeout=1.0,
            extra_env={"OTHELLO_GAMELOG_DIR": cls.log_dir.name},
        )
        cls.server.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()
        cls.log_dir.cleanup()

    def setUp(self) -> None:
        self.client = httpx.Client(base_url=self.server.base_url, timeout=15.0)

    def tearDown(self) -> None:
        self.client.close()

    def _new_game(self, color: str = "black", ai_level: int = 1) -> dict:
        response = self.client.post(
            "/api/game",
            json={"player_name": "integration_user", "player_color": color, "ai_level": ai_level},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("game_id", payload)
        self.assertIn("state", payload)
        return payload

    def test_health(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_create_game_and_state(self):
        created = self._new_game("black", 2)
        game_id = created["game_id"]
        state = created["state"]

        self.assertEqual(state["player_color"], "black")
        self.assertEqual(state["computer_color"], "white")
        self.assertEqual(state["ai_level"], 2)
        self.assertEqual(state["ai_strategy"], "negamax")
        self.assertEqual(state["ai_parameter"], 4)
        self.assertEqual(state["opponent_name"], "Raphael")
        self.assertEqual(state["opponent_portrait"], "/web/portraits/raphael.svg")
        self.assertIn("Raphael: Alright, let's do this.", " ".join(state["messages"]))
        self.assertEqual(state["next_player"], "black")
        self.assertEqual(len(state["board"]), 64)
        self.assertEqual(state["black_count"], 2)
        self.assertEqual(state["white_count"], 2)
        self.assertGreaterEqual(len(state["legal_moves"]), 4)
        self.assertEqual(state["move_record"], "")

        state_resp = self.client.get(f"/api/game/{game_id}")
        self.assertEqual(state_resp.status_code, 200)
        self.assertEqual(state_resp.json()["game_id"], game_id)

    def test_white_starts_with_computer_move(self):
        created = self._new_game("white", 4)
        state = created["state"]
        self.assertEqual(state["player_color"], "white")
        self.assertEqual(state["opponent_name"], "Donatello")
        self.assertEqual(state["move_number"], 1)
        self.assertIn("Donatello goes first...", " ".join(state["messages"]))
        self.assertEqual(state["next_player"], "white")

    def test_opponent_profiles_parameterized(self):
        expected = [
            (1, "Michelangelo", "negamax", 3, False),
            (2, "Raphael", "negamax", 4, False),
            (3, "Leonardo", "negamax", 5, False),
            (4, "Donatello", "negamax", 6, True),
            (5, "Shredder", "mcts", 10000, True),
            (6, "April", "april", 1, False),
        ]
        for ai_level, name, strategy, parameter, use_opening_book in expected:
            with self.subTest(ai_level=ai_level):
                created = self._new_game("black", ai_level)
                state = created["state"]
                self.assertEqual(state["opponent_name"], name)
                self.assertEqual(state["ai_level"], ai_level)
                self.assertEqual(state["ai_strategy"], strategy)
                self.assertEqual(state["ai_parameter"], parameter)
                self.assertEqual(state["use_opening_book"], use_opening_book)

    def test_player_move_then_computer_move_cycle(self):
        created = self._new_game("black")
        game_id = created["game_id"]

        legal_resp = self.client.get(f"/api/game/{game_id}/legal-moves")
        legal = legal_resp.json()["legal_moves"]
        self.assertTrue(legal)

        move_resp = self.client.post(f"/api/game/{game_id}/move", json={"move": legal[0]})
        self.assertEqual(move_resp.status_code, 200, move_resp.text)
        after_player = move_resp.json()
        self.assertEqual(after_player["next_player"], "white")
        self.assertRegex(after_player["move_record"], r"^[A-H][1-8]$")

        comp_resp = self.client.post(f"/api/game/{game_id}/computer-move")
        self.assertEqual(comp_resp.status_code, 200, comp_resp.text)
        after_comp = comp_resp.json()
        self.assertEqual(after_comp["next_player"], "black")
        self.assertRegex(after_comp["move_record"], r"^[A-H][1-8][a-h][1-8]$")

    def test_player_can_resign(self):
        created = self._new_game("black", 3)
        game_id = created["game_id"]

        resign_resp = self.client.post(f"/api/game/{game_id}/resign", json={"actor": "player"})
        self.assertEqual(resign_resp.status_code, 200, resign_resp.text)
        state = resign_resp.json()
        self.assertTrue(state["game_over"])
        self.assertEqual(state["winner"], "computer")
        self.assertIn("resigns", " ".join(state["messages"]).lower())
        self.assertIn("Leonardo: Victory is mine.", " ".join(state["messages"]))

    def test_computer_can_resign_with_character_phrase(self):
        created = self._new_game("black", 4)
        game_id = created["game_id"]

        resign_resp = self.client.post(f"/api/game/{game_id}/resign", json={"actor": "computer"})
        self.assertEqual(resign_resp.status_code, 200, resign_resp.text)
        state = resign_resp.json()
        self.assertTrue(state["game_over"])
        self.assertEqual(state["winner"], "player")
        self.assertIn("Donatello: Unexpected outcome.", " ".join(state["messages"]))

    def test_websocket_receives_state_update(self):
        created = self._new_game("black")
        game_id = created["game_id"]
        ws_url = f"ws://127.0.0.1:{self.server.port}/ws/game/{game_id}"

        with ws_connect(ws_url) as websocket:
            first = websocket.recv(timeout=5)
            payload = json.loads(first)
            self.assertEqual(payload["type"], "state_update")
            self.assertEqual(payload["data"]["game_id"], game_id)

    def test_stress_multiple_games_and_turns(self):
        game_count = 6
        max_rounds = 20

        for i in range(game_count):
            color = "black" if i % 2 == 0 else "white"
            created = self._new_game(color)
            game_id = created["game_id"]

            for _ in range(max_rounds):
                state_resp = self.client.get(f"/api/game/{game_id}")
                self.assertEqual(state_resp.status_code, 200)
                state = state_resp.json()
                if state["game_over"]:
                    break

                legal_resp = self.client.get(f"/api/game/{game_id}/legal-moves")
                self.assertEqual(legal_resp.status_code, 200)
                legal_payload = legal_resp.json()
                legal_moves = legal_payload["legal_moves"]
                next_player = legal_payload["next_player"]

                if not legal_moves:
                    pass_resp = self.client.post(f"/api/game/{game_id}/pass", json={})
                    self.assertEqual(pass_resp.status_code, 200, pass_resp.text)
                    continue

                if next_player == state["player_color"]:
                    chosen = random.choice(legal_moves)
                    move_resp = self.client.post(f"/api/game/{game_id}/move", json={"move": chosen})
                    self.assertEqual(move_resp.status_code, 200, move_resp.text)
                else:
                    move_resp = self.client.post(f"/api/game/{game_id}/computer-move")
                    self.assertEqual(move_resp.status_code, 200, move_resp.text)

            final_state = self.client.get(f"/api/game/{game_id}").json()
            self.assertEqual(final_state["black_count"] + final_state["white_count"], final_state["user_count"] + final_state["computer_count"])
            self.assertLessEqual(final_state["black_count"] + final_state["white_count"], 64)


if __name__ == "__main__":
    unittest.main()
