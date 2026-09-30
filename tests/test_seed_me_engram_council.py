"""Opt-in engram council for seed-me: lens answers -> settle by delegation or surface to the human.

Written before the script. The council only ever advises; a human's standing delegation is the authority.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/seed-me/scripts/engram_council.py"
SKILL = (ROOT / "skills/seed-me/SKILL.md").read_text()
TRANSITIONS = (ROOT / "skills/seed-me/references/ledger-transitions.md").read_text()
COUNCIL_DOC = ROOT / "skills/seed-me/references/engram-council.md"

DECISIONS = [
    {"id": "D1", "title": "Output surface", "options": ["terminal", "html", "both"], "undo": "cheap", "grounded": True},
    {"id": "D2", "title": "Action scope", "options": ["report-only", "delete"], "undo": "moderate", "grounded": True},
    {"id": "D3", "title": "Audience", "options": ["only me", "shareable"], "undo": "cheap", "grounded": True},
    {"id": "D4", "title": "Delete policy", "options": ["never", "ask"], "undo": "hard", "grounded": True},
    {"id": "D5", "title": "Guess", "options": ["a", "b"], "undo": "cheap", "grounded": False},
    {"id": "D6", "title": "Tie", "options": ["x", "y"], "undo": "cheap", "grounded": True},
]


def lens(rows, missing="none"):
    return "\n".join(rows) + f"\nMISSING: {missing}\n"


class Council(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        (self.dir / "decisions.json").write_text(json.dumps(DECISIONS))

    def run_script(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def decide(self, lenses):
        args = ["decide", str(self.dir / "decisions.json")]
        for name, text in lenses.items():
            path = self.dir / f"{name}.txt"
            path.write_text(text)
            args += ["--lens", f"{name}={path}"]
        done = self.run_script(*args)
        self.assertEqual(done.returncode, 0, done.stderr)
        return {d["id"]: d for d in json.loads(done.stdout)["decisions"]}, json.loads(done.stdout)

    def test_ask_prints_the_strict_prompt(self):
        done = self.run_script("ask", str(self.dir / "decisions.json"), "--idea", "a branch report")
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout
        self.assertIn("a branch report", out)
        for d in DECISIONS:
            self.assertIn(d["id"], out)
            self.assertIn(d["title"], out)
            for option in d["options"]:
                self.assertIn(option, out)
        self.assertIn("CHANGES-MEANING", out)
        self.assertIn("MISSING", out)

    def test_unanimous_choice_settles_by_delegation_with_evidence_from_each_lens(self):
        rows = ["D1 | both | CHANGES-MEANING: no | one scan", "D2 | report-only | CHANGES-MEANING: no | read-only"]
        result, _ = self.decide({"pg": lens(rows), "ka": lens(rows)})
        d1 = result["D1"]
        self.assertEqual((d1["action"], d1["choice"], d1["authority"]), ("settle", "both", "delegated"))
        self.assertFalse(d1["boundary"])
        self.assertEqual(len(d1["evidence"]), 2)
        self.assertTrue(all("simulation, not the person" in e for e in d1["evidence"]))
        self.assertIn("pg", d1["authority_source"])
        self.assertIn("standing delegation", d1["authority_source"])

    def test_unanimous_choice_with_a_meaning_flag_settles_but_is_marked_boundary(self):
        rows = ["D2 | report-only | CHANGES-MEANING: yes | boundary", ]
        other = ["D2 | report-only | CHANGES-MEANING: no | fine"]
        result, _ = self.decide({"pg": lens(rows), "ka": lens(other)})
        self.assertEqual((result["D2"]["action"], result["D2"]["boundary"]), ("settle", True))

    def test_diverging_choices_with_a_meaning_flag_surface_with_the_dissent(self):
        a = ["D3 | only me | CHANGES-MEANING: yes | personal"]
        b = ["D3 | shareable | CHANGES-MEANING: no | polish"]
        result, _ = self.decide({"pg": lens(b), "ka": lens(a), "cj": lens(a)})
        d3 = result["D3"]
        self.assertEqual(d3["action"], "surface")
        self.assertEqual(d3["reason"], "lenses diverge and at least one flags a change of meaning")
        self.assertEqual(sorted(d3["choices"]), ["cj", "ka", "pg"])
        self.assertNotIn("authority", d3)

    def test_diverging_choices_without_a_flag_settle_on_a_strict_plurality_and_tie_surfaces(self):
        a = ["D1 | both | CHANGES-MEANING: no | x", "D6 | x | CHANGES-MEANING: no | x"]
        b = ["D1 | html | CHANGES-MEANING: no | x", "D6 | y | CHANGES-MEANING: no | x"]
        c = ["D1 | both | CHANGES-MEANING: no | x", "D6 | y | CHANGES-MEANING: no | x"]
        result, _ = self.decide({"l1": lens(a), "l2": lens(a), "l3": lens(b), "l4": lens(c)})
        self.assertEqual((result["D1"]["action"], result["D1"]["choice"]), ("settle", "both"))
        self.assertEqual(result["D1"]["dissent"], ["l3"])
        self.assertEqual(result["D6"]["action"], "surface")
        self.assertEqual(result["D6"]["reason"], "no strict plurality among the lenses")

    def test_hard_to_undo_and_ungrounded_decisions_always_surface(self):
        rows = ["D4 | never | CHANGES-MEANING: no | safe", "D5 | a | CHANGES-MEANING: no | x"]
        result, _ = self.decide({"pg": lens(rows), "ka": lens(rows)})
        self.assertEqual((result["D4"]["action"], result["D4"]["reason"]), ("surface", "hard to undo: the human's instinct comes first"))
        self.assertEqual((result["D5"]["action"], result["D5"]["reason"]), ("surface", "ungrounded: cannot settle by delegation"))

    def test_malformed_lines_and_invalid_choices_abstain_and_are_recorded(self):
        good = ["D1 | both | CHANGES-MEANING: no | ok"]
        bad = ["D1 | banana | CHANGES-MEANING: no | ok", "D2 garbage"]
        result, full = self.decide({"pg": lens(good), "ka": lens(bad)})
        self.assertEqual(result["D1"]["action"], "surface")
        self.assertEqual(result["D1"]["reason"], "fewer than two valid lens answers")
        self.assertEqual(sorted(full["lenses"]["ka"]["abstained"]), ["D1", "D2", "D3", "D4", "D5", "D6"])

    def test_a_missing_decision_is_collected_not_dropped(self):
        rows = ["D1 | both | CHANGES-MEANING: no | ok"]
        _, full = self.decide({"pg": lens(rows, missing="error honesty: what does it say when state is ambiguous"), "ka": lens(rows)})
        self.assertEqual(full["missing"], [{"lens": "pg", "text": "error honesty: what does it say when state is ambiguous"}])

    def test_a_bad_decisions_file_is_a_short_error(self):
        (self.dir / "decisions.json").write_text('{"not": "a list"}')
        done = self.run_script("ask", str(self.dir / "decisions.json"), "--idea", "x")
        self.assertEqual(done.returncode, 2)
        self.assertTrue(done.stderr.startswith("engram_council: "))
        self.assertLess(done.stderr.count("\n"), 3)


class Contract(unittest.TestCase):
    def test_the_skill_documents_an_opt_in_default_off_council(self):
        self.assertIn("Opt-in: engram council", SKILL)
        self.assertIn("off by default", SKILL)
        self.assertIn("references/engram-council.md", SKILL)
        self.assertTrue(COUNCIL_DOC.is_file())

    def test_the_council_doc_states_the_authority_and_safety_rules(self):
        doc = COUNCIL_DOC.read_text()
        for needle in ["standing delegation", "never the person's own words", "hard to undo", "ungrounded",
                       "separate context", "no tools", "MISSING", "a human still confirms"]:
            self.assertIn(needle, doc)

    def test_the_ledger_rules_allow_only_an_explicit_named_standing_delegation(self):
        self.assertIn("standing delegation", TRANSITIONS)
        self.assertIn("ambiguous", TRANSITIONS)


if __name__ == "__main__":
    unittest.main()
