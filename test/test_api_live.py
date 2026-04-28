import random
import json
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

import httpx
from websockets.sync.client import connect as ws_connect


ROOT = Path(__file__).resolve().parent.parent


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LiveApiServer:
    def __init__(self) -> None:
        self.port = _find_free_port()
        self.base_url = f"http://127.0.0.1:{self.port}"
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        command = [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(self.port),
            "--log-level",
            "warning",
        ]
        self.process = subprocess.Popen(
            command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        timeout_at = time.time() + 20
        with httpx.Client(timeout=1.0) as client:
            while time.time() < timeout_at:
                if self.process.poll() is not None:
                    stdout, stderr = self.process.communicate(timeout=2)
                    raise RuntimeError(
                        f"Uvicorn exited early with code {self.process.returncode}\n"
                        f"STDOUT:\n{stdout}\nSTDERR:\n{stderr}"
                    )
                try:
                    response = client.get(f"{self.base_url}/api/health")
                    if response.status_code == 200:
                        return
                except Exception:
                    pass
                time.sleep(0.15)

        self.stop()
        raise TimeoutError("Timed out waiting for FastAPI server to become healthy")

    def stop(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process = None


class TestLiveFastApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = LiveApiServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def setUp(self) -> None:
        self.client = httpx.Client(base_url=self.server.base_url, timeout=15.0)

    def tearDown(self) -> None:
        self.client.close()

    def _new_game(self, color: str = "black", ai_depth: int = 3) -> dict:
        response = self.client.post(
            "/api/game",
            json={"player_name": "integration_user", "player_color": color, "ai_depth": ai_depth},
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
        created = self._new_game("black", 4)
        game_id = created["game_id"]
        state = created["state"]

        self.assertEqual(state["player_color"], "black")
        self.assertEqual(state["computer_color"], "white")
        self.assertEqual(state["ai_depth"], 4)
        self.assertEqual(state["opponent_name"], "Raphael")
        self.assertEqual(state["opponent_portrait"], "/web/portraits/raphael.svg")
        self.assertIn("Raphael: Alright, let's do this.", " ".join(state["messages"]))
        self.assertEqual(state["next_player"], "black")
        self.assertEqual(len(state["board"]), 64)
        self.assertEqual(state["black_count"], 2)
        self.assertEqual(state["white_count"], 2)
        self.assertGreaterEqual(len(state["legal_moves"]), 4)

        state_resp = self.client.get(f"/api/game/{game_id}")
        self.assertEqual(state_resp.status_code, 200)
        self.assertEqual(state_resp.json()["game_id"], game_id)

    def test_white_starts_with_computer_move(self):
        created = self._new_game("white", 6)
        state = created["state"]
        self.assertEqual(state["player_color"], "white")
        self.assertEqual(state["opponent_name"], "Donatello")
        self.assertEqual(state["move_number"], 1)
        self.assertIn("Donatello goes first...", " ".join(state["messages"]))
        self.assertEqual(state["next_player"], "white")

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

        comp_resp = self.client.post(f"/api/game/{game_id}/computer-move")
        self.assertEqual(comp_resp.status_code, 200, comp_resp.text)
        after_comp = comp_resp.json()
        self.assertEqual(after_comp["next_player"], "black")

    def test_player_can_resign(self):
        created = self._new_game("black", 5)
        game_id = created["game_id"]

        resign_resp = self.client.post(f"/api/game/{game_id}/resign", json={"actor": "player"})
        self.assertEqual(resign_resp.status_code, 200, resign_resp.text)
        state = resign_resp.json()
        self.assertTrue(state["game_over"])
        self.assertEqual(state["winner"], "computer")
        self.assertIn("resigns", " ".join(state["messages"]).lower())
        self.assertIn("Leonardo: Victory is mine.", " ".join(state["messages"]))

    def test_computer_can_resign_with_character_phrase(self):
        created = self._new_game("black", 6)
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
