import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent.parent


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


class LiveUiServer:
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

        timeout_at = time.time() + 25
        with httpx.Client(timeout=1.2) as client:
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
        raise TimeoutError("Timed out waiting for backend server")

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


class TestUiPlaywright(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = LiveUiServer()
        cls.server.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def test_black_player_can_start_and_make_move(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.server.base_url, wait_until="domcontentloaded")

            page.get_by_test_id("name-input").fill("UI Tester")
            page.get_by_test_id("color-black").click()
            page.get_by_test_id("opponent-select").select_option("5")
            page.get_by_test_id("start-game").click()

            page.get_by_test_id("board").wait_for(state="visible", timeout=10000)
            page.get_by_test_id("opponent-name").wait_for(state="visible", timeout=10000)
            self.assertEqual(page.get_by_test_id("opponent-name").inner_text().strip(), "Leonardo")
            self.assertIn("Depth 5", page.get_by_test_id("opponent-depth").inner_text())
            self.assertIn("Focus. Begin.", page.get_by_test_id("opponent-opening-phrase").inner_text())
            portrait_src = page.get_by_test_id("opponent-portrait").get_attribute("src") or ""
            self.assertIn("/web/portraits/leonardo.svg", portrait_src)
            self.assertGreaterEqual(page.locator(".files-top span").count(), 8)
            self.assertGreaterEqual(page.locator(".ranks span").count(), 8)
            page.wait_for_function(
                "() => document.querySelectorAll('.cell.legal').length >= 1",
                timeout=10000,
            )

            initial_move = int(page.get_by_test_id("move-number").inner_text())
            page.locator(".cell.legal").first.click()

            page.wait_for_function(
                "(before) => Number(document.querySelector('[data-testid=\"move-number\"]').textContent) > before",
                arg=initial_move,
                timeout=10000,
            )
            page.get_by_test_id("opponent-opening-phrase").wait_for(state="hidden", timeout=10000)

            page.wait_for_function(
                "() => document.querySelectorAll('.cell.last-player-move').length >= 1",
                timeout=10000,
            )

            page.wait_for_function(
                "() => document.querySelectorAll('[data-testid=\"messages\"] li').length >= 3",
                timeout=10000,
            )

            status_text = page.get_by_test_id("status-line").inner_text().lower()
            self.assertTrue("turn" in status_text or "thinking" in status_text)
            browser.close()

    def test_white_player_starts_after_computer_move(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.server.base_url, wait_until="domcontentloaded")

            page.get_by_test_id("name-input").fill("White UI")
            page.get_by_test_id("color-white").click()
            page.get_by_test_id("opponent-select").select_option("4")
            page.get_by_test_id("start-game").click()

            page.get_by_test_id("board").wait_for(state="visible", timeout=10000)
            page.wait_for_function(
                "() => Number(document.querySelector('[data-testid=\"move-number\"]').textContent) >= 1",
                timeout=10000,
            )
            page.wait_for_function(
                "() => [...document.querySelectorAll('[data-testid=\"messages\"] li')].some((li) => li.textContent.includes('Raphael goes first'))",
                timeout=10000,
            )
            self.assertEqual(page.get_by_test_id("opponent-name").inner_text().strip(), "Raphael")
            next_player = page.get_by_test_id("next-player").inner_text().strip().lower()
            self.assertIn(next_player, ["black", "white"])

            page.get_by_test_id("resign-game").click()
            page.wait_for_function(
                "() => document.querySelector('[data-testid=\"winner-line\"]').textContent.toLowerCase().includes('condolences')",
                timeout=10000,
            )
            page.get_by_test_id("restart-game").click()
            page.get_by_test_id("setup-panel").wait_for(state="visible", timeout=10000)

    def test_help_modal_opens_and_closes(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.server.base_url, wait_until="domcontentloaded")

            # Verify help modal is initially hidden
            help_modal = page.locator("#help-modal")
            self.assertTrue(help_modal.evaluate("el => el.classList.contains('hidden')"))

            # Click the help button
            help_btn = page.locator("#help-btn")
            help_btn.click()

            # Wait for modal to appear and verify it's visible
            help_modal.wait_for(state="visible", timeout=5000)
            self.assertFalse(help_modal.evaluate("el => el.classList.contains('hidden')"))

            # Verify Splinter's wisdom text is present
            help_text = page.locator(".help-text").inner_text()
            self.assertIn("Attend, my students", help_text)
            self.assertIn("Othello", help_text)
            self.assertIn("contest of balance and foresight", help_text)
            self.assertIn("patience and wisdom", help_text)

            # Verify Splinter portrait is visible
            splinter_portrait = page.locator(".help-portrait")
            self.assertTrue(splinter_portrait.is_visible())
            portrait_src = splinter_portrait.get_attribute("src") or ""
            self.assertIn("splinter.svg", portrait_src)

            # Close modal by clicking close button
            close_btn = page.locator("#close-help")
            close_btn.click()

            # Verify modal is hidden
            help_modal.wait_for(state="hidden", timeout=5000)
            self.assertTrue(help_modal.evaluate("el => el.classList.contains('hidden')"))

            # Open modal again and close via Escape key
            help_btn.click()
            help_modal.wait_for(state="visible", timeout=5000)
            page.keyboard.press("Escape")

            # Verify modal closes
            help_modal.wait_for(state="hidden", timeout=5000)
            self.assertTrue(help_modal.evaluate("el => el.classList.contains('hidden')"))

            browser.close()
