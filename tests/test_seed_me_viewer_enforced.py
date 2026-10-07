"""End-to-end: the viewer is always made and its use is enforced by the session scripts, not by prose.

Everything here drives the real CLIs as subprocesses. Contract: every init/publish/end leaves a current
ledger-view.html; completing a session requires a viewer record (viewer.py was started) or an explicit
--no-viewer reason; `status` tells an agent in one call whether the viewer is live."""
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

import seed_fixture
from test_seed_me_session import node, session


SKILL = Path(__file__).resolve().parents[1] / "skills/seed-me"
SESSION = SKILL / "scripts/session.py"
VIEWER = SKILL / "scripts/viewer.py"


def run(*args):
    return subprocess.run([sys.executable, *map(str, args)], capture_output=True, text=True, timeout=30)


class TestViewerEnforced(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        made = run(SESSION, "init", "--root", self.temp.name)
        self.assertEqual(made.returncode, 0, made.stderr)
        self.directory = Path(json.loads(made.stdout)["session"])

    def publish_goal(self):
        ledger = session.load(self.directory)
        state = session.editable(ledger)
        state.update(goal="Recover data", origin="goal")
        state["draft"] = {"goal": "Recover data", "outcome": "A backup", "options": ["Export — simple"]}
        state["nodes"] = [node("goal", answer="Recover data"), node("format")]
        payload = self.directory / "update.json"
        payload.write_text(json.dumps({"state": state, "expected_version": ledger["version"],
                                       "reason": "User confirmed the goal"}))
        done = run(SESSION, "publish", self.directory, payload)
        self.assertEqual(done.returncode, 0, done.stderr)

    def settle_all(self):
        ledger = session.load(self.directory)
        state = session.editable(ledger)
        state["nodes"] = [node("goal", answer="Recover data"), node("format", answer="JSON")]
        state["current_question"] = None
        payload = self.directory / "update.json"
        payload.write_text(json.dumps({"state": state, "expected_version": ledger["version"],
                                       "reason": "User chose JSON"}))
        self.assertEqual(run(SESSION, "publish", self.directory, payload).returncode, 0)
        seed_fixture.save_seed(session, self.directory)

    def snapshot_is_current(self):
        page = (self.directory / "ledger-view.html").read_text()
        embedded = json.dumps(session.load(self.directory), ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")
        return embedded in page

    def test_every_init_publish_and_end_leaves_a_current_view(self):
        self.assertTrue(self.snapshot_is_current(), "init must leave a view")
        self.publish_goal()
        self.assertTrue(self.snapshot_is_current(), "publish must refresh the view")
        self.settle_all()
        done = run(SESSION, "end", self.directory, "--status", "completed", "--reason", "Confirmed and saved",
                   "--no-viewer", "no background processes in this host")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.snapshot_is_current(), "end must save the final view")
        self.assertIn('"status": "completed"', (self.directory / "ledger-view.html").read_text().replace('"status":"completed"', '"status": "completed"'))

    def test_completion_without_a_viewer_or_a_stated_reason_is_refused(self):
        self.publish_goal()
        self.settle_all()
        refused = run(SESSION, "end", self.directory, "--status", "completed", "--reason", "Confirmed and saved")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("viewer", refused.stderr)
        self.assertEqual(session.load(self.directory)["status"], "active")
        blank = run(SESSION, "end", self.directory, "--status", "completed", "--reason", "Confirmed", "--no-viewer", "  ")
        self.assertEqual(blank.returncode, 1)
        self.assertEqual(session.load(self.directory)["status"], "active")

    def test_a_stated_reason_completes_and_is_recorded(self):
        self.publish_goal()
        self.settle_all()
        done = run(SESSION, "end", self.directory, "--status", "completed", "--reason", "Confirmed and saved",
                   "--no-viewer", "loopback blocked in this sandbox")
        self.assertEqual(done.returncode, 0, done.stderr)
        record = json.loads((self.directory / "viewer.json").read_text())
        self.assertEqual(record["declined"], "loopback blocked in this sandbox")
        self.assertIn("declined", json.loads(run(SESSION, "status", self.directory).stdout)["viewer"])

    def test_stopping_needs_no_viewer(self):
        self.publish_goal()
        done = run(SESSION, "end", self.directory, "--status", "stopped", "--reason", "User stopped the interview")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_live_viewer_satisfies_completion_and_status_reports_it(self):
        self.publish_goal()
        server = subprocess.Popen([sys.executable, str(VIEWER), str(self.directory)], stdout=subprocess.PIPE, text=True)
        self.addCleanup(server.stdout.close)
        self.addCleanup(server.wait)
        self.addCleanup(server.terminate)
        url = server.stdout.readline().strip()
        self.assertTrue(url.startswith("http://127.0.0.1:"), url)
        record = json.loads((self.directory / "viewer.json").read_text())
        self.assertEqual((record["pid"], record["url"]), (server.pid, url))
        status = json.loads(run(SESSION, "status", self.directory).stdout)
        self.assertEqual(status["viewer"], f"live {url}")
        self.assertEqual((status["open"], status["settled"], status["snapshot_current"]), (1, 1, True))
        self.settle_all()
        done = run(SESSION, "end", self.directory, "--status", "completed", "--reason", "Confirmed and saved")
        self.assertEqual(done.returncode, 0, done.stderr)
        server.terminate()
        server.wait(timeout=10)
        time.sleep(0.2)
        self.assertEqual(json.loads(run(SESSION, "status", self.directory).stdout)["viewer"], "started earlier, not running now")

    def test_a_viewer_that_cannot_open_a_port_says_what_to_do_instead(self):
        self.publish_goal()
        taken = socket.socket()
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        self.addCleanup(taken.close)
        before = (self.directory / "ledger.json").read_bytes()
        failed = run(VIEWER, self.directory, "--port", taken.getsockname()[1])
        self.assertEqual(failed.returncode, 1)
        for needed in ("could not open a local port", "--no-viewer", "ledger-view.html"):
            self.assertIn(needed, failed.stderr)
        self.assertNotEqual(failed.stderr.strip(), "[Errno 48] Address already in use")
        self.assertFalse((self.directory / "viewer.json").exists(), "a viewer that never started leaves no record")
        self.assertEqual((self.directory / "ledger.json").read_bytes(), before)
        self.assertTrue(self.snapshot_is_current())
        self.assertEqual(json.loads(run(SESSION, "status", self.directory).stdout)["viewer"], "not started")

    def test_status_is_one_compact_answer_for_the_agent(self):
        self.publish_goal()
        out = run(SESSION, "status", self.directory)
        self.assertEqual(out.returncode, 0, out.stderr)
        status = json.loads(out.stdout)
        self.assertEqual(set(status), {"status", "revision", "version", "open", "settled", "current_question",
                                       "viewer", "snapshot", "snapshot_current"})
        self.assertEqual(status["viewer"], "not started")
        self.assertTrue(status["snapshot"].endswith("ledger-view.html"))
        self.assertLess(len(out.stdout), 600)


class TestSkillTextMatchesTheEnforcement(unittest.TestCase):
    def setUp(self):
        self.skill = (SKILL / "SKILL.md").read_text()
        self.lean = (SKILL / "references/lean-path.md").read_text()

    def test_the_viewer_is_started_by_default_not_offered(self):
        self.assertNotIn("only if the user says yes", self.skill)
        self.assertIn("--no-viewer", self.skill)
        self.assertIn('session.py" status', self.skill)

    def test_both_paths_share_startup_without_changing_authority_or_handoff(self):
        for text in (self.skill, self.lean):
            self.assertNotIn("no session, ledger, or viewer", text)
            self.assertNotIn("skip the session, ledger, and viewer", text)
        self.assertIn("On both Lean and Full", self.skill)
        self.assertIn("start the session and viewer", self.lean)
        self.assertIn("Session lifecycle", self.lean)
        self.assertIn("Human edits are never overwritten", self.lean)
        self.assertIn("not approval to implement", self.lean)
        self.assertIn("no automatic Markdown import", self.lean)
        self.assertIn("The folder is the handoff", self.skill)
        self.assertIn("contract revision", self.lean)
        self.assertIn("do not bypass", self.skill)
        mode = (SKILL / "references/agent-mode.md").read_text()
        self.assertIn('Both paths: `python3 "<skill>/scripts/session.py" init --operator simulated`', mode)
        self.assertNotIn("Full path:", mode)

    def test_the_ledger_reference_is_read_only_after_choosing_full(self):
        self.assertNotIn("Before opening the interview, read [ledger-transitions.md]", self.skill)
        full = self.skill.split("### Size gate", 1)[1]
        self.assertIn("ledger-transitions.md", full)
        self.assertLess(self.skill.index("### Size gate"), self.skill.index("ledger-transitions.md", self.skill.index("### Size gate")))

    def test_a_check_for_something_not_built_yet_may_be_provisional_and_does_not_block(self):
        rule = self.skill.split("- Acceptance criteria:", 1)[1].split("- Affected users and systems", 1)[0]
        for needed in ("does not exist yet", "provisional:", "do not block confirmation", "never reported as verification"):
            self.assertIn(needed, rule)
        self.assertIn("downstream stages consume it verbatim", rule, "the executable-core rule for existing interfaces stays")
        self.assertIn("provisional:", self.lean.split("## Acceptance checks", 1)[1])

    def test_lean_questions_may_be_plain_when_no_real_choice_exists(self):
        self.assertIn("factual", self.lean.split("5. One question at a time", 1)[1].split("6.", 1)[0])

    def test_the_money_exclusion_is_defined_by_exposure(self):
        gate = self.lean.split("Lean only if", 1)[1].split("The agent proposes", 1)[0]
        self.assertNotIn("data loss, money, or public exposure", gate)
        self.assertIn("financial", gate)


if __name__ == "__main__":
    unittest.main()
