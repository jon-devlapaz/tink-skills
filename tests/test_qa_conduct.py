import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("seed_me_conduct", ROOT / "qa/seed_me_conduct.py")
conduct = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(conduct)
sys.path.insert(0, str(ROOT / "skills/seed-me/scripts"))
import session  # noqa: E402

GOOD = """Question 1 of 1 ready (0 waiting on earlier answers)
❓ **Trash method: how should it move a file to the Trash?**

**What I found:** the Trash folder exists.

**Option A: ask Finder.** Tradeoff: Put Back works. If you pick B instead: no permission prompt. Undo cost: **cheap.**
**Option B: plain move.** Tradeoff: simpler. If you pick A instead: a prompt. Undo cost: **moderate.**

Against my suggestion: Finder adds a permission dependency.
➡️ **My suggestion: A.** Confidence: medium. Observed: the folder exists. Inferred: Put Back works. Would flip if: the prompt blocks you. Not checked: I did not test it. My number to change: none.
Ledger: file:///tmp/x/seed-contract.md"""

INSTINCT = """Question 1 (1 more waiting after this)
❓ **May the tool ever delete anything?**

**What I found:** three files are over 200 MB.

**What's your instinct?** One line is enough."""


def statuses(text, operator=False):
    return {rule: status for rule, (status, _) in conduct.turn_findings(text, operator).items()}


class TestTurnRules(unittest.TestCase):
    def test_a_good_option_turn_passes_every_rule(self):
        self.assertTrue(conduct.is_option_turn(GOOD))
        self.assertEqual({s for s in statuses(GOOD).values()}, {"pass"})

    def test_each_defect_is_caught(self):
        defects = {
            "two-options": GOOD.replace("Option B", "Choice B"),
            "undo-cost": GOOD.replace("Undo cost: **cheap.**", "Undo cost: if wrong you lose files."),
            "against-line": GOOD.replace("Against my suggestion:", "Note:"),
            "calibration": GOOD.replace("Confidence: medium.", "Confidence: medium-high."),
            "names-not-ids": GOOD.replace("Trash method", "Q3 Trash method"),
            "single-question": GOOD + "\n❓ another question?",
            "ledger-footer": GOOD.replace("Ledger: file:///tmp/x/seed-contract.md", ""),
            "length": GOOD + "\n" + "word " * 500,
        }
        for rule, text in defects.items():
            with self.subTest(rule=rule):
                self.assertEqual(statuses(text)[rule], "fail", rule)

    def test_calibration_names_the_missing_field(self):
        detail = conduct.turn_findings(GOOD.replace("Not checked: I did not test it. ", ""))["calibration"][1]
        self.assertIn("Not checked:", detail)

    def test_instinct_turn_must_not_show_options_or_a_suggestion(self):
        self.assertTrue(conduct.is_instinct_turn(INSTINCT))
        self.assertEqual(statuses(INSTINCT)["instinct-first-pure"], "pass")
        leaky = INSTINCT + "\n**Option A: never.** ➡️ My suggestion: A"
        self.assertEqual(statuses(leaky)["instinct-first-pure"], "fail")

    def test_prose_that_discusses_options_is_not_a_question_turn(self):
        report = "I compared Option A (report only) with Option B (remove too) and my suggestion was A. Confidence: high."
        self.assertFalse(conduct.is_question_turn(report))
        quoting = 'The rule is: ask "What\'s your instinct?" first, then show the options.'
        self.assertFalse(conduct.is_question_turn(quoting))

    def test_operator_messages_must_not_leak_internals(self):
        clean = {r: s for r, (s, _) in conduct.turn_findings("Here is the draft. What do you want to change?", True).items()}
        self.assertEqual(clean["operator-no-leak"], "pass")
        for leak in ("The ledger says so.", "Run session.py", "your authority is simulated", "see SKILL.md"):
            with self.subTest(leak=leak):
                self.assertEqual(conduct.turn_findings(leak, True)["operator-no-leak"][0], "fail")


class TestTranscriptReading(unittest.TestCase):
    def test_reads_chat_text_and_sendmessage_bodies_with_recipient_and_since(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "t.jsonl"
            entries = [
                {"type": "assistant", "timestamp": "2026-09-28T10:00:00", "message": {"content": [{"type": "text", "text": "old"}]}},
                {"type": "assistant", "timestamp": "2026-09-29T10:00:00", "message": {"content": [
                    {"type": "text", "text": "new chat"},
                    {"type": "tool_use", "name": "SendMessage", "input": {"to": "agent1", "message": "to operator"}},
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}}]}},
                {"type": "user", "timestamp": "2026-09-29T10:01:00", "message": {"content": "ignored"}},
            ]
            path.write_text("\n".join(json.dumps(e) for e in entries) + "\nnot json\n")
            turns = list(conduct.read_turns(path, since="2026-09-29"))
            self.assertEqual([(k, t) for _, k, t in turns], [("user-facing", "new chat"), ("sent:agent1", "to operator")])
            self.assertEqual(len(list(conduct.read_turns(path))), 3)


class TestLedgerRules(unittest.TestCase):
    def make(self, decisions):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        directory = session.create(Path(temp.name))
        state = session.editable(session.load(directory))
        goal = {"id": "goal", "kind": "decision", "status": "settled", "prerequisites": [], "evidence": [], "owner": "You",
                "gate": "confirm", "answer": "Ship it", "authority": "user", "authority_source": 'chat: "yes"'}
        nodes = [goal]
        for name, authority, source in decisions:
            node = {"id": name, "kind": "decision", "status": "settled", "prerequisites": ["goal"], "evidence": ["x.py:1"] if authority == "delegated" else [],
                    "owner": "You", "gate": "pick", "answer": name, "authority": authority, "authority_source": source}
            nodes.append(node)
        state.update(goal="Ship it", origin="goal", nodes=nodes)
        session.publish(directory, state, 0, "test fixture")
        return directory

    def test_sources_must_quote_words_and_a_delegation_needs_a_quote(self):
        directory = self.make([("a", "user", "interview turn 1"), ("b", "delegated", "Jev p=1.0; research ranks #1"),
                               ("c", "delegated", "chat: 'recommended'"), ("d", "user", 'chat: "I want d"')])
        detail = conduct.ledger_findings(directory)["source-cites-user-words"]
        self.assertEqual(detail[0], "fail")
        self.assertIn("b", detail[1])
        self.assertNotIn(" a,", detail[1] + ",")
        self.assertTrue(conduct.cites_user_words("interview turn 1", "user"))
        self.assertFalse(conduct.cites_user_words("interview turn 1", "delegated"))

    def test_high_acceptance_rate_is_flagged_only_with_enough_decisions(self):
        arrow = 'chat: "your arrow"'
        flagged = self.make([(n, "delegated", arrow) for n in "abc"])
        self.assertEqual(conduct.ledger_findings(flagged)["accept-rate"][0], "fail")
        mixed = self.make([("a", "delegated", arrow), ("b", "user", 'chat: "b"'), ("c", "user", 'chat: "c"')])
        self.assertEqual(conduct.ledger_findings(mixed)["accept-rate"][0], "pass")
        few = self.make([("a", "delegated", arrow), ("b", "delegated", arrow)])
        self.assertEqual(conduct.ledger_findings(few)["accept-rate"][0], "pass")

    def test_an_invalid_ledger_is_reported_not_crashed_on(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp) / "ledger.json").write_text("{}")
            self.assertEqual(conduct.ledger_findings(temp)["valid-ledger"][0], "fail")


class TestContractRules(unittest.TestCase):
    def check(self, text, name="seed-contract.md"):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / name
            path.write_text(text)
            return {r: s for r, (s, _) in conduct.contract_findings(path).items()}

    BODY = """# Seed contract
## You are confirming
- Goal: x
## Knowledge map
- What we know, with proof: E1 (observed 2026-09-29)
- What we know we don't know: growth rate, owner: you
- What is true but nobody has read: the PR bodies
- What could surprise us:
  Probe: pre-mortem — answer: it lists a worktree that is in use — changed: added an in-use verdict
  Probe: counter-example — answer: a repo with no remote — changed: nothing
  Probe: outside view — answer: skipped by the user — changed: nothing (skipped by the user)
  Where we did not look: other machines and repos outside ~/dev/active
  We would know we were wrong if: a verdict says safe and the branch turns out unpushed
## Acceptance checks
1. **Listed.** cmd: `ls` | expect: files | cwd: any
2. **A person reads it.** Human-only: cannot run automatically.
## Evidence
"""

    def test_a_well_formed_contract_passes(self):
        self.assertEqual(set(self.check(self.BODY).values()), {"pass"})

    def test_each_contract_defect_is_caught(self):
        self.assertEqual(self.check(self.BODY.replace("cmd: `ls`", "`ls`"))["check-lines"], "fail")
        self.assertEqual(self.check(self.BODY.replace(" | cwd: any", ""))["check-lines"], "fail")
        self.assertEqual(self.check(self.BODY.replace("## You are confirming", "## Summary"))["confirming-box"], "fail")
        self.assertEqual(self.check(self.BODY, "seed-contract.simulated.md")["simulated-labelled"], "fail")
        simulated = self.BODY + "Status: simulated — not confirmed by a human\n"
        self.assertEqual(self.check(simulated, "seed-contract.simulated.md")["simulated-labelled"], "pass")
        self.assertEqual(self.check(simulated)["simulated-labelled"], "fail")

    def test_the_knowledge_map_must_show_real_probes_and_limits(self):
        self.assertEqual(self.check(self.BODY)["knowledge-map"], "pass")
        defects = {
            "no section": self.BODY.replace("## Knowledge map", "## Notes"),
            "missing part": self.BODY.replace("- What is true but nobody has read: the PR bodies\n", ""),
            "too few probes": self.BODY.replace("  Probe: counter-example — answer: a repo with no remote — changed: nothing\n", ""),
            "probe without answer": self.BODY.replace("answer: it lists a worktree that is in use — ", ""),
            "no limits": self.BODY.replace("  Where we did not look: other machines and repos outside ~/dev/active\n", ""),
            "empty limits": self.BODY.replace("other machines and repos outside ~/dev/active", ""),
            "no wrong-signal": self.BODY.replace("We would know we were wrong if:", "Nothing else:"),
        }
        for label, text in defects.items():
            with self.subTest(label):
                self.assertEqual(self.check(text)["knowledge-map"], "fail", label)

    def test_a_suffix_on_the_heading_and_a_preface_line_are_tolerated(self):
        text = self.BODY.replace("## Acceptance checks", "## Acceptance checks (placeholders)\nAll are proposals.\n")
        self.assertEqual(self.check(text)["check-lines"], "pass")


if __name__ == "__main__":
    unittest.main()
