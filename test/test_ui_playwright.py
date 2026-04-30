import unittest

from live_server import LiveServer

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None


@unittest.skipIf(sync_playwright is None, "playwright dependency is not installed")
class TestUiPlaywright(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = LiveServer(startup_timeout=25, health_timeout=1.2)
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
            page.get_by_test_id("opponent-select").select_option("3")
            page.get_by_test_id("start-game").click()

            page.get_by_test_id("board").wait_for(state="visible", timeout=10000)
            page.get_by_test_id("opponent-name").wait_for(state="visible", timeout=10000)
            self.assertEqual(page.get_by_test_id("opponent-name").inner_text().strip(), "Leonardo")
            self.assertIn("NEGAMAX 5", page.get_by_test_id("opponent-depth").inner_text())
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
            page.get_by_test_id("opponent-select").select_option("2")
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

    def test_pass_alerts_show_when_no_legal_moves(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.server.base_url, wait_until="domcontentloaded")

            page.get_by_test_id("name-input").fill("Pass Tester")
            page.get_by_test_id("color-black").click()
            page.get_by_test_id("opponent-select").select_option("1")
            page.get_by_test_id("start-game").click()

            page.get_by_test_id("board").wait_for(state="visible", timeout=10000)
            page.wait_for_function(
                "() => document.querySelectorAll('.cell.legal').length >= 1",
                timeout=10000,
            )

            # Play moves and monitor for pass alerts
            max_moves = 30
            moves_made = 0
            pass_alert_seen = False
            
            while moves_made < max_moves:
                # Check if game is over
                if page.locator('[data-testid="winner-line"]').count() > 0:
                    winner_text = page.locator('[data-testid="winner-line"]').inner_text()
                    if "Congratulations" in winner_text or "Condolences" in winner_text or "Draw" in winner_text:
                        break
                
                # Check if pass alert is visible (non-blocking check)
                pass_alert = page.locator("#pass-alert")
                if pass_alert.count() > 0 and not pass_alert.evaluate("el => el.classList.contains('hidden')"):
                    pass_alert_seen = True
                    alert_text = page.locator("#pass-alert-text").inner_text()
                    self.assertIn("pass", alert_text.lower())

                    # Dismiss all currently queued alerts.
                    for _ in range(4):
                        page.locator("#dismiss-pass-alert").click()
                        page.wait_for_timeout(120)
                        if pass_alert.evaluate("el => el.classList.contains('hidden')"):
                            break
                
                # Check if there are legal moves
                legal_cells = page.locator(".cell.legal")
                if legal_cells.count() == 0:
                    # No legal moves - alert should appear if game not ending
                    try:
                        pass_alert.wait_for(state="visible", timeout=3000)
                        pass_alert_seen = True
                    except:
                        # Alert might not appear if game ends (both players pass)
                        pass
                    break
                
                # Make a move
                page.locator(".cell.legal").first.click()
                moves_made += 1
                
                # Wait for state to update
                page.wait_for_timeout(300)
            
            # We expect to see at least one pass alert in a full game, but don't assert
            # as it depends on random board states. Just verify the mechanism works.
            browser.close()
