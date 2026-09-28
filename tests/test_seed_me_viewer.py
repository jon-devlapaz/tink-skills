import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from test_seed_me_session import node, session


SCRIPT = Path(__file__).resolve().parents[1] / "skills/seed-me/scripts/viewer.py"
SPEC = importlib.util.spec_from_file_location("seed_viewer", SCRIPT)
viewer = importlib.util.module_from_spec(SPEC)
sys.path.insert(0, str(SCRIPT.parent))
try:
    SPEC.loader.exec_module(viewer)
finally:
    sys.path.pop(0)


class ViewerFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = session.create(self.temp.name)
        self.server = viewer.make_server(self.directory)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def publish(self, state, reason="Synthetic test fixture transition"):
        return session.publish(self.directory, state, session.load(self.directory)["version"], reason)

    def confirm(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Recover data", origin="goal", current_question="backup")
        state["nodes"] = [node("goal", answer="Recover data"),
                          node("import-behavior", "fact", answer="Replace existing data"),
                          {**node("backup", parents=["import-behavior"]), "question": "Require a backup?"},
                          node("button-label", answer="Import backup")]
        return self.publish(state)


class TestViewerHTTP(ViewerFixture, unittest.TestCase):
    def test_serves_only_viewer_and_validated_ledger(self):
        (self.directory / "private.txt").write_text("not exposed")
        with urlopen(self.url + "/ledger-view.html") as response:
            self.assertIn(b"Draft", response.read())
            self.assertEqual(response.headers["Cache-Control"], "no-store")
        with urlopen(self.url + "/ledger.json?poll=1") as response:
            self.assertEqual(json.load(response)["origin"], None)
        for path in ("/private.txt", "/.writer.lock", "/../ledger.json", "/%2e%2e/ledger.json"):
            with self.subTest(path=path), self.assertRaises(HTTPError) as raised:
                urlopen(self.url + path)
            self.assertEqual(raised.exception.code, 404)
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertEqual((self.directory / "ledger-view.html").read_text(),
                         viewer.snapshot_page(session.load(self.directory)))

    def test_bad_host_mutation_and_corrupt_data_fail_closed(self):
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.url + "/ledger.json", headers={"Host": "attacker.example"}))
        self.assertEqual(raised.exception.code, 403)
        before = (self.directory / "ledger.json").read_bytes()
        with self.assertRaises(HTTPError) as raised:
            urlopen(Request(self.url + "/ledger.json", data=b"{}", method="POST"))
        self.assertEqual(raised.exception.code, 501)
        self.assertEqual((self.directory / "ledger.json").read_bytes(), before)
        (self.directory / "ledger.json").write_text("{")
        with self.assertRaises(HTTPError) as raised:
            urlopen(self.url + "/ledger.json")
        self.assertEqual(raised.exception.code, 503)


class TestViewerSnapshots(ViewerFixture, unittest.TestCase):
    def test_snapshot_is_atomic_and_escapes_script_boundaries(self):
        state = session.editable(session.load(self.directory))
        attack = '</script><script>window.injected=true</script>'
        state["draft"]["goal"] = attack
        self.publish(state)
        before = (self.directory / "ledger-view.html").read_bytes()
        with patch.object(session.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                viewer.save_snapshot(self.directory)
        self.assertEqual((self.directory / "ledger-view.html").read_bytes(), before)
        path = viewer.save_snapshot(self.directory)
        html = path.read_text()
        self.assertNotIn(attack, html)
        embedded = re.search(r'<script id="ledger-data" type="application/json">\s*(.*?)\s*</script>', html, re.S)
        self.assertEqual(json.loads(embedded.group(1)), session.load(self.directory))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_ended_viewer_cli_saves_snapshot_without_a_server(self):
        self.confirm()
        ended = session.end(self.directory, "stopped", "User stopped")
        for args in ([], ["--snapshot"]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SCRIPT), str(self.directory), *args],
                                        capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), (self.directory / "ledger-view.html").as_uri())
                self.assertEqual(session.load(self.directory), ended)


class TestViewerBrowser(ViewerFixture, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from playwright.sync_api import sync_playwright, expect
        except ImportError:
            raise unittest.SkipTest("Browser checks require Python Playwright and Chromium or Google Chrome")
        cls.expect = staticmethod(expect)
        cls.playwright = sync_playwright().start()
        try:
            try:
                cls.browser = cls.playwright.chromium.launch(headless=True)
            except Exception:
                cls.browser = cls.playwright.chromium.launch(channel="chrome", headless=True)
        except Exception as error:
            cls.playwright.stop()
            raise unittest.SkipTest(f"No launchable Chromium or Google Chrome: {error}")

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        super().setUp()
        self.context = self.browser.new_context()
        self.addCleanup(self.context.close)
        self.context.route("**/cytoscape.min.js", lambda route: route.abort())
        self.page = self.context.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))

    def test_live_draft_decision_answer_and_reopening_with_safe_history(self):
        state = session.editable(session.load(self.directory))
        attack = '<img src=x onerror="window.injected=true">'
        state["draft"] = {"goal": attack, "outcome": "Recover data", "options": ["Export", "Import"]}
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#draft")).to_be_visible()
        self.expect(self.page.locator("#draft-content")).to_contain_text(attack)
        self.expect(self.page.locator("#ledger-list")).to_contain_text("No accepted goal")
        self.assertEqual(self.page.locator("#draft img").count(), 0)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        self.confirm()
        self.expect(self.page.locator("#draft")).to_be_hidden()
        self.expect(self.page.locator("#current")).to_have_text("Current question: Require a backup?")
        self.expect(self.page.locator("#counts")).to_contain_text("1 decision ready")
        self.expect(self.page.locator("#detail")).to_contain_text("unresolved")
        state = session.editable(session.load(self.directory))
        state["nodes"][2].update(status="settled", answer=attack, authority="user", authority_source="fixture conversation: chose backup")
        state["current_question"] = None
        self.publish(state)
        self.expect(self.page.locator("#detail")).to_contain_text(attack)
        self.expect(self.page.locator("#counts")).to_contain_text("2 settled")
        state = session.editable(session.load(self.directory))
        state["nodes"][1].update(answer="Merge data", evidence=["fixture import.py:10: merge(existing, incoming)"])
        state["nodes"][2] = {**node("backup", parents=["import-behavior"]), "question": "Still require a backup?",
                              "reopen_reason": "Import behavior changed from replace to merge"}
        state["current_question"] = "backup"
        self.publish(state, "Fixture evidence changed from replace to merge")
        self.expect(self.page.locator("#current")).to_have_text("Current question: Still require a backup?")
        self.expect(self.page.locator("#detail > dl")).to_contain_text("unresolved")
        self.expect(self.page.locator("#detail .history").first).to_contain_text(attack)
        self.expect(self.page.locator("#detail .history").first).to_contain_text("changed from replace to merge")
        self.expect(self.page.locator('[data-node-id="button-label"]')).to_contain_text("Import backup")
        self.assertEqual(self.page.locator("#detail img, #ledger-list img").count(), 0)
        self.assertIsNone(self.page.evaluate("window.injected"))
        self.assertEqual(self.errors, [])

    def test_complete_fallback_and_selected_detail_refresh_without_reload(self):
        self.confirm()
        self.page.goto(self.url)
        self.expect(self.page.locator("#cdn-banner")).to_be_visible()
        section = self.page.locator('[data-node-id="import-behavior"]')
        section.locator("summary").click()
        section.get_by_role("button", name="Inspect node").click()
        self.expect(self.page.locator("#detail")).to_contain_text("Replace existing data")
        self.expect(self.page.locator("#detail")).to_contain_text("import.py:10")
        state = session.editable(session.load(self.directory))
        state["nodes"][1].update(answer="Merge data", evidence=["fixture import.py:10: merge()"])
        self.publish(state, "Fresh fixture evidence")
        self.expect(self.page.locator("#detail > dl")).to_contain_text("Merge data")
        self.expect(self.page.locator("#detail .history")).to_contain_text("Replace existing data")
        self.expect(section).to_have_attribute("open", "")
        self.assertEqual(self.errors, [])

    def test_graph_tracks_real_dependencies_and_clicked_node_history(self):
        library = os.environ.get("SEED_ME_CYTOSCAPE_PATH")
        if not library or not Path(library).is_file():
            self.skipTest("Set SEED_ME_CYTOSCAPE_PATH to the SRI-pinned Cytoscape file for offline graph checks")
        self.context.unroute("**/cytoscape.min.js")
        self.context.route("**/cytoscape.min.js", lambda route: route.fulfill(path=library, content_type="application/javascript"))
        self.page.goto(self.url)
        self.page.wait_for_function("LEDGER !== null && cy === null")
        self.confirm()
        self.page.wait_for_function("cy !== null && cy.nodes().length === 3")
        self.assertEqual(self.page.evaluate("cy.getElementById('goal').length"), 0)
        self.expect(self.page.locator("#cdn-banner")).to_be_hidden()
        self.expect(self.page.locator("#cy canvas").first).to_be_visible()
        self.assertEqual(self.page.evaluate("cy.edges().map(e => [e.source().id(), e.target().id()])"),
                         [["import-behavior", "backup"]])
        self.assertTrue(self.page.evaluate("cy.getElementById('backup').hasClass('current')"))
        position = self.page.evaluate("cy.getElementById('backup').renderedPosition()")
        self.page.locator("#cy").click(position=position)
        self.expect(self.page.locator("#detail h2")).to_have_text("backup")
        state = session.editable(session.load(self.directory))
        state["nodes"][2].update(status="settled", answer="Require backup", authority="user", authority_source="fixture chat: yes")
        state["current_question"] = None
        self.publish(state)
        self.page.wait_for_function("cy.getElementById('backup').hasClass('settled')")
        state = session.editable(session.load(self.directory))
        state["nodes"][1].update(answer="Merge data", evidence=["fixture: merges may overwrite keys"])
        state["nodes"][2] = {**node("backup", parents=["import-behavior"]),
                              "reopen_reason": "Import behavior changed from replace to merge"}
        state["current_question"] = "backup"
        self.publish(state, "Fixture changed premise")
        self.page.wait_for_function("cy.getElementById('backup').hasClass('current')")
        self.expect(self.page.locator("#detail > dl")).to_contain_text("unresolved")
        self.expect(self.page.locator("#detail .history").first).to_contain_text("Require backup")
        self.assertTrue(self.page.evaluate("cy.getElementById('button-label').hasClass('settled')"))
        self.assertEqual(self.errors, [])

    def test_graph_is_hidden_when_every_edge_only_points_at_the_goal(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="first")
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("first", parents=["goal"]), "question": "First?"},
                          {**node("second", parents=["goal"]), "question": "Second?"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#call")).to_contain_text("First?")
        self.expect(self.page.locator("main")).to_be_hidden()
        self.assertIsNone(self.page.evaluate("cy"))
        self.expect(self.page.locator("#cdn-banner")).to_be_hidden()
        self.assertEqual(self.errors, [])

    def test_parked_concern_says_what_it_is_waiting_on(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="first")
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("first", parents=["goal"]), "question": "First?", "label": "Pick the store"},
                          {**node("second", parents=["first"]), "question": "Second?"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#open-list")).to_contain_text("Second?")
        self.expect(self.page.locator("#open-list")).to_contain_text("Waiting on: Pick the store")
        self.expect(self.page.locator("#open-list")).not_to_contain_text("goal")
        self.assertEqual(self.errors, [])

    def test_deferred_concern_shows_its_revisit_condition_and_bare_card_makes_no_false_claim(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        state["nodes"] = [node("goal", answer="Ship it"),
                          {**node("now", parents=["goal"]), "question": "Bare question?"},
                          {**node("later", parents=["goal"]), "status": "deferred", "question": "Later?",
                           "defer_reason": "not blocking", "revisit_condition": "after v1 ships"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#deferred-list")).to_contain_text("Revisit: after v1 ships")
        self.expect(self.page.locator("#call")).not_to_contain_text("replaces the recommendation")
        self.expect(self.page.locator("#call")).to_contain_text("Reply in chat with your answer")
        self.assertEqual(self.errors, [])

    def test_many_settled_items_fold_so_open_work_stays_visible(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal", current_question="now")
        settled = [node(f"s{i}", answer=f"Answer {i}") for i in range(1, 13)]
        for item in settled:
            item["label"] = f"Settled {item['id'][1:]}"
        state["nodes"] = [node("goal", answer="Ship it"), *settled,
                          {**node("now", parents=["goal"]), "question": "Still to decide?"},
                          {**node("later", parents=["goal"]), "question": "Open one?", "label": "Open one"}]
        self.publish(state)
        self.page.goto(self.url)
        self.expect(self.page.locator("#settled-list > li")).to_have_count(5)
        self.expect(self.page.locator("#settled-list > li").first).to_contain_text("Settled 12")
        self.expect(self.page.locator("#settled-more-sum")).to_have_text("Show 7 earlier settled")
        self.expect(self.page.locator("#settled-more")).not_to_have_attribute("open", "")
        self.expect(self.page.locator("#open-list")).to_contain_text("Open one")
        self.assertEqual(self.errors, [])

    def test_saved_ended_view_is_read_only_offline_and_after_restart(self):
        self.confirm()
        self.page.goto(self.url)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        state = session.editable(session.load(self.directory))
        state["nodes"][3]["answer"] = '</script><script>window.injected=true</script>'
        self.publish(state)
        ended = session.end(self.directory, "stopped", "User stopped")
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "ended")
        snapshot = viewer.save_snapshot(self.directory)
        self.server.shutdown()
        self.page.goto(snapshot.as_uri())
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "ended")
        self.expect(self.page.locator("#connection")).to_contain_text("Interview stopped")
        self.expect(self.page.locator('[data-node-id="backup"]')).to_contain_text("unresolved")
        self.assertIsNone(self.page.evaluate("window.injected"))
        self.assertIsNone(self.page.evaluate("timer"))
        self.assertEqual(session.load(self.directory), ended)
        self.assertEqual(self.errors, [])

    def test_active_offline_snapshot_does_not_start_polling(self):
        self.confirm()
        snapshot = viewer.save_snapshot(self.directory)
        self.page.goto(snapshot.as_uri())
        self.expect(self.page.locator("#connection")).to_contain_text("read-only")
        self.expect(self.page.locator("#current")).to_contain_text("Require a backup?")
        self.assertIsNone(self.page.evaluate("timer"))
        self.assertEqual(self.errors, [])

    def test_failed_poll_retains_state_and_same_snapshot_recovers(self):
        self.confirm()
        self.page.goto(self.url)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        original = (self.directory / "ledger.json").read_bytes()
        (self.directory / "ledger.json").write_text("{")
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "error")
        self.expect(self.page.locator("#connection")).to_contain_text("last valid snapshot")
        self.expect(self.page.locator("#current")).to_contain_text("Require a backup?")
        (self.directory / "ledger.json").write_bytes(original)
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "live")
        state = session.editable(session.load(self.directory))
        state.update(status="stopped", current_question=None)
        self.publish(state, "Fixture user stopped interview")
        self.expect(self.page.locator("#connection")).to_have_attribute("data-health", "ended")
        (self.directory / "ledger.json").write_text("{")
        self.page.wait_for_timeout(2300)
        self.expect(self.page.locator("#connection")).to_contain_text("Interview stopped")
        self.assertEqual(self.errors, [])

    def test_validate_rejects_untrusted_ledger_fields(self):
        self.confirm()
        self.page.goto(self.url)
        base = session.load(self.directory)
        def envelope(nodes):
            return {"nodes": nodes, "frontier": base["frontier"], "origin": base["origin"], "goal": base["goal"], "current_question": base["current_question"], "draft": base["draft"]}
        unresolved = json.loads(json.dumps(base["nodes"]))
        for entry in unresolved:
            if entry["id"] == "backup":
                entry.pop("owner", None)
                entry.pop("gate", None)
        wrong_authority = json.loads(json.dumps(base["nodes"]))
        for entry in wrong_authority:
            if entry["id"] == "import-behavior":
                entry["authority"] = "user"
        blank_evidence = json.loads(json.dumps(base["nodes"]))
        for entry in blank_evidence:
            if entry["id"] == "import-behavior":
                entry["evidence"] = [""]
        cases = [("unresolved decision missing owner/gate", envelope(unresolved)), ("settled fact with user authority", envelope(wrong_authority)), ("settled fact with blank evidence", envelope(blank_evidence))]
        for name, ledger in cases:
            with self.subTest(name=name):
                with self.assertRaises(Exception):
                    self.page.evaluate(f"validate({json.dumps(ledger)})")


if __name__ == "__main__":
    unittest.main()
