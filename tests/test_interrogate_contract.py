"""Structural contract checks for interrogate.

These checks must not be reported as proof of transition or authorization behavior.
"""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "interrogate"


class TestGrillMeWithJevContract(unittest.TestCase):
    def test_skill_identity_and_metadata(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        frontmatter = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        self.assertIsNotNone(frontmatter)
        fields = dict(line.split(":", 1) for line in frontmatter.group(1).splitlines())
        self.assertEqual(fields["name"].strip(), SKILL_DIR.name)
        self.assertTrue(fields["description"].strip())
        self.assertRegex(fields["  version"].strip().strip('"'), r"^\d+\.\d+\.\d+$")

    def test_pre_intent_handoff_contract(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        self.assertIn("repository-root `pre-intent.md`", content)
        self.assertNotIn("grill-plan.md", content)
        for required in (
            "confirmed for intake",
            "not approved for implementation",
            "Problem statement",
            "Proposed outcome",
            "Acceptance criteria",
            "exact command",
            "Suggested first slice",
            "Affected users and systems",
            "Constraints and boundaries",
            "Accepted decisions",
            "Evidence and uncertainty",
            "Risks and verification",
            "Open questions and deferrals",
            "Do not preselect a downstream profile or fabricate stage approval",
        ):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_operational_references_resolve_inside_skill(self):
        links = []
        for path in SKILL_DIR.rglob("*.md"):
            for href in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
                if "://" in href or href.startswith("#"):
                    continue
                target = (path.parent / unquote(href.split("#")[0])).resolve()
                self.assertTrue(target.is_relative_to(SKILL_DIR.resolve()), target)
                self.assertTrue(target.is_file(), target)
                links.append(target)
        for ref_name in ("ledger-transitions.md",):
            with self.subTest(ref=ref_name):
                self.assertIn(SKILL_DIR / "references" / ref_name, links)
        self.assertNotIn(SKILL_DIR / "references" / "typesafe-protocol.md", links)

    def test_no_triage_machinery(self):
        # Per-turn lens routing is allowed (see test_lens_call_present); the
        # banned set is the triage/option/Noul machinery rejected by pilots.
        # Revision note: narrowed from a blanket model-advice ban by explicit
        # operator direction; see run grill-epistemic dogfood battery report.
        for path in SKILL_DIR.rglob("*.md"):
            content = path.read_text()
            for token in ("typesafe-protocol", "Jev triage", "Jev option",
                          "Noul", "noul", "\u26a1",
                          "grill-me-with-jev"):
                with self.subTest(path=str(path), token=token):
                    self.assertNotIn(token, content)

    def test_lens_call_present(self):
        self.assertTrue((SKILL_DIR / "references" / "epistemic-lenses.md").is_file())
        content = (SKILL_DIR / "SKILL.md").read_text()
        for required in ("epistemic-lenses.md", "gating rule",
                         "never a badge"):
            with self.subTest(required=required):
                self.assertIn(required, content)
        lenses = (SKILL_DIR / "references" / "epistemic-lenses.md").read_text()
        for required in ("Opt-in", "Authorization", "Preflight",
                         "unresolved", "transcript is the receipt",
                         "confidence", "0.50"):
            with self.subTest(required=required):
                self.assertIn(required, lenses)

    def test_braindump_entry_and_draft_step(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        for required in ("braindump", "Shape the working draft",
                         "PROVISIONAL", "Only then does the frontier loop"):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_single_presentation_template(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        self.assertEqual(len(re.findall(r"```text", content)), 1)
        self.assertIn("\U0001f4dc Grounded:", content)
        self.assertIn("\U0001f464 Owner:", content)

    def test_ledger_viewer_asset(self):
        viewer = SKILL_DIR / "assets" / "ledger-view.html"
        self.assertTrue(viewer.is_file())
        sidecar = SKILL_DIR / "assets" / "ledger.json"
        self.assertTrue(sidecar.is_file())
        html = viewer.read_text()
        for required in ("cytoscape", "cdnjs.cloudflare.com", "integrity=\"sha384-",
                         "ledger-data", "__LEDGER_JSON__", "breadthfirst",
                         "fetch('ledger.json", "setInterval(poll", "origin", "classes: cls(n)", "cdn-banner", "fallback()"):
            with self.subTest(required=required):
                self.assertIn(required, html)
        import json
        data = json.loads(sidecar.read_text())
        self.assertIn(data["origin"], [n["id"] for n in data["nodes"]])
        skill = (SKILL_DIR / "SKILL.md").read_text()
        self.assertIn("assets/ledger-view.html", skill)
        self.assertIn("localhost", skill)
        ledger = (SKILL_DIR / "references" / "ledger-transitions.md").read_text()
        self.assertIn("JSON serialization", ledger)
        self.assertIn("origin", ledger)

    # docs/ chain retired with the docs tree (prune): no design docs ship;
    # runs/ carry session evidence instead.


if __name__ == "__main__":
    unittest.main()
