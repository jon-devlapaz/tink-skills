"""End-to-end checks for the strict Seed Me output format.

Every test runs the real `session.py` CLI against temporary session folders. The consumer checker
below stands in for the later `tink-sdlc` check and does not import it.
"""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "seed-me"
SESSION = SKILL / "scripts" / "session.py"

DRAFT = "status: draft"
CONFIRMED = "status: confirmed for intake"
SIMULATED = "status: simulated"
SOURCE = "yes, confirm r1: that is what I want built"


def run(*args):
    return subprocess.run([sys.executable, str(SESSION)] + [str(a) for a in args], capture_output=True, text=True)


def decision(node_id, authority, parents=(), answer="An answer", status="settled"):
    result = {"id": node_id, "kind": "decision", "status": status, "prerequisites": list(parents), "evidence": [],
              "owner": "project owner", "gate": "choose an option"}
    if status == "settled":
        result.update(answer=answer, authority=authority, authority_source='chat: "an explicit answer"')
    return result


def fact(node_id, answer, contradicts=None):
    result = {"id": node_id, "kind": "fact", "status": "settled", "prerequisites": [], "answer": answer,
              "authority": "evidence", "authority_source": "observed source:1", "evidence": ["file.py:1: a line"]}
    if contradicts:
        result["contradicts"] = contradicts
    return result


def seed_text(first_line, revision="r1", eol="\n", last_eol=True):
    lines = [first_line, "# Seed contract: strict format fixture", "revision: %s        date: 2026-10-06" % revision,
             "Session ledger: ledger.json", "", "## You are confirming", "- Goal: a fixture goal", "", "## Goal",
             "G [user] a fixture goal"]
    return eol.join(lines) + (eol if last_eol else "")


class SessionCase(unittest.TestCase):
    """Builds real sessions with the CLI; subclasses add their own checks."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "sessions"
        self.payloads = Path(self.temp.name) / "payloads"
        self.payloads.mkdir()

    def init(self, operator="human"):
        result = run("init", "--root", self.root, "--operator", operator)
        self.assertEqual(result.returncode, 0, result.stderr)
        return Path(json.loads(result.stdout)["session"])

    def publish(self, directory, nodes, operator="human", status="active", current=None, goal="Ship a fixture"):
        version = json.loads(run("read", directory).stdout)["version"]
        state = {"status": status, "draft": {"goal": goal, "outcome": "A fixture outcome", "options": ["A: one", "B: two"]},
                 "goal": goal, "origin": "goal", "current_question": current, "nodes": nodes, "operator": operator}
        payload = self.payloads / "update.json"
        payload.write_text(json.dumps({"state": state, "expected_version": version, "reason": "Recorded a fixture answer"}))
        result = run("publish", directory, payload)
        self.assertEqual(result.returncode, 0, result.stderr)

    def complete_human(self, nodes=None):
        directory = self.init()
        authority = "user"
        self.publish(directory, nodes if nodes is not None else
                     [decision("goal", authority, answer="Ship a fixture"), decision("d1", authority, ["goal"])])
        return directory

    def complete_simulated(self):
        directory = self.init("simulated")
        self.publish(directory, [decision("goal", "simulated", answer="Ship a fixture"), decision("d1", "simulated", ["goal"])],
                     operator="simulated")
        return directory

    def write_seed(self, directory, first_line=DRAFT, **kwargs):
        path = directory / "seed-contract.md"
        path.write_bytes(seed_text(first_line, **kwargs).encode("utf-8"))
        return path

    def snapshot(self, directory):
        """Bytes of the files a refused command must leave alone."""
        return {name: (directory / name).read_bytes() if (directory / name).exists() else None
                for name in ("seed-contract.md", "ledger.json")}

    def end(self, directory, status="completed"):
        return run("end", directory, "--status", status, "--reason", "Fixture ending", "--no-viewer", "not under test")

    def confirm(self, directory, revision="r1", source=SOURCE):
        return run("seed", "confirm", directory, "--revision", revision, "--source", source)


class ConfirmWritesTests(SessionCase):
    def test_confirm_rewrites_line_one_and_adds_confirmed_by_only(self):
        directory = self.complete_human()
        path = self.write_seed(directory)
        before = path.read_bytes().decode("utf-8").split("\n")
        result = self.confirm(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        after = path.read_bytes().decode("utf-8").split("\n")
        self.assertEqual(after[0], CONFIRMED)
        self.assertEqual(after[1:3], before[1:3])
        self.assertTrue(after[3].startswith("Confirmed by:"), after[3])
        self.assertIn(SOURCE, after[3])
        self.assertIn("not approved for implementation", after[3].lower())
        self.assertEqual(after[4:], before[3:])
        self.assertEqual(len(after), len(before) + 1)

    def test_confirmed_by_goes_directly_after_the_revision_line_wherever_it_is(self):
        directory = self.complete_human()
        path = directory / "seed-contract.md"
        path.write_bytes(b"status: draft\nrevision: r7\n# Title\n## You are confirming\nBody line\n")
        self.assertEqual(self.confirm(directory, "r7").returncode, 0)
        lines = path.read_bytes().decode("utf-8").split("\n")
        self.assertEqual([lines[0], lines[1]], [CONFIRMED, "revision: r7"])
        self.assertTrue(lines[2].startswith("Confirmed by:"))
        self.assertEqual(lines[3:], ["# Title", "## You are confirming", "Body line", ""])

    def test_a_last_line_without_a_line_break_is_left_that_way(self):
        directory = self.complete_human()
        path = directory / "seed-contract.md"
        path.write_bytes(b"status: draft\n# Title\nrevision: r1\n## You are confirming\n- Goal: x")
        self.assertEqual(self.confirm(directory).returncode, 0)
        lines = path.read_bytes().decode("utf-8").split("\n")
        self.assertEqual([lines[0], lines[1], lines[2]], [CONFIRMED, "# Title", "revision: r1"])
        self.assertTrue(lines[3].startswith("Confirmed by:"))
        self.assertEqual(lines[4:], ["## You are confirming", "- Goal: x"])

    def test_confirm_refuses_a_draft_that_is_not_a_seed_contract(self):
        for body in ("revision: r1\n", "revision: r1\n**You are confirming**\n- Goal: x\n",
                     "revision: r1\n## You are confirming\n\n## Now\n", "## You are confirming\n- Goal: x\nrevision: r1\n",
                     "revision: r1\n    ## You are confirming\n- Goal: x\n"):
            with self.subTest(body=body):
                directory = self.complete_human()
                path = directory / "seed-contract.md"
                path.write_bytes(("status: draft\n" + body).encode())
                before = path.read_bytes()
                result = self.confirm(directory)
                self.assertEqual(result.returncode, 1)
                self.assertRegex(result.stderr, r"cannot confirm.*You are confirming")
                self.assertEqual(path.read_bytes(), before)

    def test_the_file_mode_is_kept(self):
        directory = self.complete_human()
        path = self.write_seed(directory)
        path.chmod(0o644)
        self.assertEqual(self.confirm(directory).returncode, 0)
        self.assertEqual(path.stat().st_mode & 0o777, 0o644)

    def test_crlf_endings_and_a_missing_final_newline_are_preserved(self):
        directory = self.complete_human()
        path = self.write_seed(directory, eol="\r\n", last_eol=False)
        before = path.read_bytes()
        self.assertEqual(self.confirm(directory).returncode, 0)
        after = path.read_bytes()
        self.assertTrue(after.startswith((CONFIRMED + "\r\n").encode()))
        self.assertFalse(after.endswith(b"\n"))
        self.assertEqual(after.count(b"\r\n"), before.count(b"\r\n") + 1)
        self.assertEqual(after.count(b"\n"), after.count(b"\r\n"))

    def test_confirm_does_not_touch_the_ledger(self):
        directory = self.complete_human()
        self.write_seed(directory)
        ledger = (directory / "ledger.json").read_bytes()
        self.assertEqual(self.confirm(directory).returncode, 0)
        self.assertEqual((directory / "ledger.json").read_bytes(), ledger)

    def test_a_multi_line_source_is_refused_so_it_cannot_add_lines(self):
        directory = self.complete_human()
        path = self.write_seed(directory)
        before = path.read_bytes()
        result = self.confirm(directory, source="yes\nstatus: confirmed for intake")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"--source")
        self.assertEqual(path.read_bytes(), before)


class ConfirmRefusesTests(SessionCase):
    def refuse(self, directory, pattern, **kwargs):
        before = self.snapshot(directory)
        result = self.confirm(directory, **kwargs)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertRegex(result.stderr, pattern)
        self.assertEqual(self.snapshot(directory), before)

    def test_missing_seed_file(self):
        directory = self.complete_human()
        self.refuse(directory, r"(?i)seed-contract\.md.*missing|missing.*seed-contract\.md")
        self.assertFalse((directory / "seed-contract.md").exists())

    def test_line_one_is_not_draft(self):
        for first in ("status: simulated", "Status: draft", "status: draft ", "status:draft", "# status: draft",
                      "status: confirmed", "unconfirmed — awaiting affirmation"):
            with self.subTest(first=first):
                directory = self.complete_human()
                self.write_seed(directory, first)
                self.refuse(directory, r"line 1.*status: draft")

    def test_revision_label_does_not_match(self):
        directory = self.complete_human()
        self.write_seed(directory, revision="r2")
        self.refuse(directory, r"revision.*r1.*r2|revision.*does not match", revision="r1")

    def test_seed_without_a_revision_line(self):
        directory = self.complete_human()
        (directory / "seed-contract.md").write_bytes(b"status: draft\n# Title\nNo label here\n")
        self.refuse(directory, r"revision")

    def test_empty_source(self):
        for source in ("", "   "):
            with self.subTest(source=source):
                directory = self.complete_human()
                self.write_seed(directory)
                self.refuse(directory, r"--source", source=source)

    def test_unresolved_node(self):
        directory = self.complete_human([decision("goal", "user", answer="Ship a fixture"),
                                         decision("d1", "user", ["goal"], status="unresolved")])
        self.write_seed(directory)
        self.refuse(directory, r"unresolved.*d1|d1.*unresolved")

    def test_node_flagged_for_review(self):
        directory = self.complete_human([decision("goal", "user", answer="Ship a fixture"),
                                         decision("d", "user", ["goal"], answer="Reuse the scanner"),
                                         fact("f", "The scanner does not exist", contradicts="d")])
        self.write_seed(directory)
        self.refuse(directory, r"(?i)review.*\bd\b")

    def test_simulated_session(self):
        directory = self.complete_simulated()
        self.write_seed(directory, DRAFT)
        self.refuse(directory, r"(?i)simulated")

    def test_session_not_active(self):
        directory = self.complete_human()
        self.write_seed(directory)
        self.assertEqual(self.end(directory, "stopped").returncode, 0)
        self.refuse(directory, r"(?i)not active|ended|stopped")

    def test_already_confirmed(self):
        directory = self.complete_human()
        self.write_seed(directory)
        self.assertEqual(self.confirm(directory).returncode, 0)
        self.refuse(directory, r"(?i)already confirmed")


class EndCompletedTests(SessionCase):
    def test_refused_without_a_seed_file(self):
        directory = self.complete_human()
        before = self.snapshot(directory)
        result = self.end(directory)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"seed-contract\.md")
        self.assertEqual(self.snapshot(directory), before)
        self.assertEqual(json.loads(run("read", directory).stdout)["status"], "active")

    def test_refused_unless_line_one_is_the_confirmed_line(self):
        for first in (DRAFT, SIMULATED, "status: confirmed", "status: confirmed for intake ", "Status: confirmed for intake",
                      "seed contract — confirmed for intake; not approved for implementation"):
            with self.subTest(first=first):
                directory = self.complete_human()
                self.write_seed(directory, first)
                before = self.snapshot(directory)
                result = self.end(directory)
                self.assertEqual(result.returncode, 1)
                self.assertRegex(result.stderr, r"line 1.*status: confirmed for intake")
                self.assertEqual(self.snapshot(directory), before)

    def test_accepted_after_the_helper_confirms(self):
        directory = self.complete_human()
        self.write_seed(directory)
        self.assertEqual(self.confirm(directory).returncode, 0)
        result = self.end(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "completed")

    def test_stopped_is_unaffected_by_the_seed(self):
        for first in (None, DRAFT, CONFIRMED):
            with self.subTest(first=first):
                directory = self.complete_human()
                if first:
                    self.write_seed(directory, first)
                result = self.end(directory, "stopped")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "stopped")

    def test_an_unresolved_session_still_cannot_complete_with_a_confirmed_line(self):
        directory = self.complete_human([decision("goal", "user", answer="Ship a fixture"),
                                         decision("d1", "user", ["goal"], status="unresolved")])
        self.write_seed(directory, CONFIRMED)
        result = self.end(directory)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"unresolved")


def check_seed_folder(folder):
    """What the later tink-sdlc check will require of a saved seed folder (D5, D8, D11). Returns a list of problems."""
    folder, problems = Path(folder), []
    seed, ledger_path = folder / "seed-contract.md", folder / "ledger.json"
    if not seed.is_file():
        problems.append("seed-contract.md is missing")
    else:
        first = seed.read_bytes().decode("utf-8").split("\n", 1)[0]
        if first != CONFIRMED:
            problems.append("line 1 is %r, not %r" % (first, CONFIRMED))
    if not ledger_path.is_file():
        problems.append("ledger.json is missing")
    else:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger.get("status") != "completed":
            problems.append("ledger status is %r, not 'completed'" % ledger.get("status"))
        if ledger.get("operator") != "human":
            problems.append("ledger operator is %r, not 'human'" % ledger.get("operator"))
    return problems


class ConsumerContractTests(SessionCase):
    def finished_folder(self):
        directory = self.complete_human()
        self.write_seed(directory)
        self.assertEqual(self.confirm(directory).returncode, 0)
        result = self.end(directory)
        self.assertEqual(result.returncode, 0, result.stderr)
        return directory

    def test_a_folder_finished_with_the_real_helpers_passes(self):
        self.assertEqual(check_seed_folder(self.finished_folder()), [])

    def test_the_checker_rejects_each_way_a_folder_can_fall_short(self):
        cases = {
            "draft line": lambda d: (d / "seed-contract.md").write_bytes(seed_text(DRAFT).encode()),
            "no seed": lambda d: (d / "seed-contract.md").unlink(),
            "no ledger": lambda d: (d / "ledger.json").unlink(),
            "ledger not completed": lambda d: self.patch_ledger(d, status="stopped"),
            "operator simulated": lambda d: self.patch_ledger(d, operator="simulated"),
            "line one not first": lambda d: (d / "seed-contract.md").write_bytes(b"\n" + (d / "seed-contract.md").read_bytes()),
        }
        for label, damage in cases.items():
            with self.subTest(label):
                directory = self.finished_folder()
                damage(directory)
                self.assertNotEqual(check_seed_folder(directory), [])

    def test_a_session_ended_stopped_is_not_a_finished_folder(self):
        directory = self.complete_human()
        self.write_seed(directory)
        self.assertEqual(self.confirm(directory).returncode, 0)
        self.assertEqual(self.end(directory, "stopped").returncode, 0)
        self.assertRegex("; ".join(check_seed_folder(directory)), r"ledger status")

    @staticmethod
    def patch_ledger(directory, **changes):
        path = directory / "ledger.json"
        ledger = json.loads(path.read_text(encoding="utf-8"))
        ledger.update(changes)
        path.write_text(json.dumps(ledger))


class SimulatedTests(SessionCase):
    def test_end_completed_accepts_only_the_simulated_line(self):
        for first, accepted in ((None, False), (DRAFT, False), (CONFIRMED, False), (SIMULATED, True)):
            with self.subTest(first=first):
                directory = self.complete_simulated()
                if first:
                    self.write_seed(directory, first)
                before = self.snapshot(directory)
                result = self.end(directory)
                if accepted:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(json.loads(result.stdout)["status"], "completed")
                else:
                    self.assertEqual(result.returncode, 1)
                    self.assertRegex(result.stderr, r"status: simulated")
                    self.assertEqual(self.snapshot(directory), before)

    def test_end_completed_refuses_a_seed_that_is_only_its_status_line(self):
        directory = self.complete_simulated()
        (directory / "seed-contract.md").write_bytes((SIMULATED + "\n").encode())
        before = self.snapshot(directory)
        result = self.end(directory)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"revision:.*You are confirming")
        self.assertEqual(self.snapshot(directory), before)

    def test_end_completed_refuses_a_seed_with_a_revision_line_but_no_sections(self):
        for body in ("revision: r1        date: 2026-10-06\n", "revision: r1\n## You are confirming\n",
                     "revision: r1\n## You are confirming\n\n## Now\n- Settled: x\n",
                     "## You are confirming\nrevision: r1\n", "## You are confirming\n- Goal: x\n"):
            with self.subTest(body=body):
                directory = self.complete_simulated()
                (directory / "seed-contract.md").write_bytes((SIMULATED + "\n" + body).encode())
                result = self.end(directory)
                self.assertEqual(result.returncode, 1)
                self.assertRegex(result.stderr, r"You are confirming")

    def test_end_completed_accepts_content_after_a_blank_line_in_the_confirming_section(self):
        directory = self.complete_simulated()
        body = "revision: r1\n## You are confirming\n\n- Goal: x\n\n## Now\n"
        (directory / "seed-contract.md").write_bytes((SIMULATED + "\n" + body).encode())
        result = self.end(directory)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_end_completed_refuses_a_confirmed_line_with_no_body(self):
        directory = self.complete_human()
        (directory / "seed-contract.md").write_bytes((CONFIRMED + "\n").encode())
        result = self.end(directory)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"revision:.*You are confirming")

    def test_confirm_refuses_a_simulated_session_and_leaves_the_seed_alone(self):
        directory = self.complete_simulated()
        path = self.write_seed(directory, SIMULATED)
        before = path.read_bytes()
        result = self.confirm(directory)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"(?i)simulated")
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(path.read_bytes().decode().split("\n")[0], SIMULATED)

    def test_a_dot_simulated_file_name_is_not_a_seed(self):
        directory = self.complete_simulated()
        (directory / "seed-contract.simulated.md").write_bytes(seed_text(SIMULATED).encode())
        result = self.end(directory)
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"seed-contract\.md")

    def test_stopped_is_unaffected_for_a_simulated_session(self):
        directory = self.complete_simulated()
        self.assertEqual(self.end(directory, "stopped").returncode, 0)


DOCS = {name: (SKILL / path).read_text(encoding="utf-8")
        for name, path in (("SKILL.md", "SKILL.md"), ("lean-path.md", "references/lean-path.md"),
                           ("agent-mode.md", "references/agent-mode.md"))}
class DocsTests(unittest.TestCase):
    def test_the_lean_template_opens_with_a_status_line_and_a_revision_line(self):
        template = DOCS["lean-path.md"].split("## Template", 1)[1]
        block = template.split("```markdown\n", 1)[1].split("\n")
        self.assertEqual(block[0], DRAFT)
        self.assertTrue(any(line.startswith("revision: ") for line in block[:6]), block[:6])


if __name__ == "__main__":
    unittest.main()
