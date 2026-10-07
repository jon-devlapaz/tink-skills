"""Structural contract checks for seed-me.

These checks must not be reported as proof of transition or authorization behavior.
"""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "seed-me"


def skill_with_seed_contract():
    """SKILL.md plus the seed-contract reference it points to."""
    return (SKILL_DIR / "SKILL.md").read_text() + "\n" + (SKILL_DIR / "references" / "seed-contract.md").read_text()


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
        content = skill_with_seed_contract()
        self.assertIn("`<session>/seed-contract.md`", content)
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
        # The banned set is the triage/option/Noul machinery rejected by pilots.
        # Revision note: narrowed from a blanket model-advice ban by explicit
        # operator direction; see run grill-epistemic dogfood battery report.
        for path in SKILL_DIR.rglob("*.md"):
            content = path.read_text()
            for token in ("typesafe-protocol", "Jev triage", "Jev option",
                          "Noul", "noul", "\u26a1",
                          "grill-me-with-jev"):
                with self.subTest(path=str(path), token=token):
                    self.assertNotIn(token, content)

    def test_single_presentation_template(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        self.assertEqual(len(re.findall(r"```text", content)), 1)
        self.assertIn("\U0001f4dc What I found:", content)
        self.assertIn("\U0001f464 Owner:", content)

    def test_lean_path_exists_and_its_template_has_the_required_parts(self):
        lean = SKILL_DIR / "references" / "lean-path.md"
        self.assertTrue(lean.is_file())
        text = lean.read_text()
        for required in ("You are confirming", "status: draft", "[evidence]", "cmd: `<exact command>`"):
            with self.subTest(lean=required):
                self.assertIn(required, text)

    def test_lean_template_has_the_sections_the_conduct_checker_reads(self):
        lean = (SKILL_DIR / "references" / "lean-path.md").read_text()
        for required in ("## Knowledge map", "Probe:", "Where we did not look:", "We would know we were wrong if:"):
            with self.subTest(lean=required):
                self.assertIn(required, lean)

    def test_ledger_viewer_asset(self):
        viewer = SKILL_DIR / "assets" / "ledger-view.html"
        self.assertTrue(viewer.is_file())
        sidecar = SKILL_DIR / "assets" / "ledger.json"
        self.assertTrue(sidecar.is_file())
        html = viewer.read_text()
        for required in ("cytoscape", "cdnjs.cloudflare.com", "integrity=\"sha384-",
                         "ledger-data", "__LEDGER_JSON__", "function layered(", "name: 'preset'",
                         "fetch('ledger.json", "setInterval(poll", "origin", "classes: cls(n)", "cdn-banner", "fallback()"):
            with self.subTest(required=required):
                self.assertIn(required, html)
        import json
        data = json.loads(sidecar.read_text())
        self.assertEqual(data["schema_version"], 1)
        self.assertIsNone(data["origin"])
        self.assertIsNone(data["goal"])
        self.assertEqual(data["nodes"], [])
        self.assertEqual(data["frontier"], [])
        skill = (SKILL_DIR / "SKILL.md").read_text()
        self.assertIn("assets/ledger-view.html", skill)
        self.assertIn("localhost", skill)
        ledger = (SKILL_DIR / "references" / "ledger-transitions.md").read_text()
        self.assertIn("JSON serialization", ledger)
        self.assertIn("origin", ledger)
        self.assertIn("Origin Is Pinned", ledger)
        self.assertIn("rename", skill)

    def test_session_lifecycle_uses_validated_helpers(self):
        skill = skill_with_seed_contract()
        ledger = (SKILL_DIR / "references/ledger-transitions.md").read_text()
        self.assertNotIn("python3 -m http.server", skill)
        self.assertNotIn("every later node descends from it", ledger)
        for required in ('scripts/session.py" init', 'scripts/session.py" read',
                         'scripts/session.py" publish', 'scripts/session.py" end',
                         'scripts/viewer.py"', "--snapshot", "process handle",
                         "stop only the recorded viewer", "outside the repository",
                         "the session folder is the handoff"):
            with self.subTest(required=required):
                self.assertIn(required, skill)
        for required in ("expected_version", "authority_source", "reopen_reason",
                         "helper-owned", "history", "Publication payload"):
            with self.subTest(required=required):
                self.assertIn(required, ledger)


class TestThroughlineSkillOrder(unittest.TestCase):
    def test_readme_throughline_order(self):
        readme = (ROOT / "README.md").read_text()
        mermaid = re.search(r"```mermaid\n(.*?)```", readme, re.DOTALL)
        self.assertIsNotNone(mermaid)
        diagram = mermaid.group(1)
        edges = (
            'intent["intent / idea"] --> seed_me["seed-me"]',
            'seed_me -->|settled seed contract| scout["skill-scout"]',
            'scout -->|qualified skill / none| implementation["ai-native-sdlc"]',
        )
        positions = []
        for edge in edges:
            at = diagram.find(edge)
            self.assertGreaterEqual(at, 0, edge)
            positions.append(at)
        self.assertEqual(positions, sorted(positions))
        self.assertLess(positions[0], positions[1])
        self.assertLess(positions[1], positions[2])
        self.assertNotIn("grill-me-with-jev", diagram)
        self.assertNotRegex(diagram, r"seed_me\s*-->(?:\|[^|]*\|)?\s*implementation\[")
        self.assertNotIn("grill-me", readme)

    def test_grill_me_with_jev_is_removed(self):
        self.assertFalse((ROOT / "skills" / "grill-me-with-jev").exists())
        for relative in (".tink/skills.toml", ".tink/skills.lock", "README.md"):
            text = (ROOT / relative).read_text()
            with self.subTest(path=relative):
                self.assertNotIn("grill-me", text)


    def test_readme_question_example_matches_the_skill_format(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Question 1 of 3 ready (2 waiting on earlier answers)", readme)
        self.assertNotRegex(readme, r"Q\d+ — ")

    def test_origin_instruction_names_the_simulated_authority(self):
        skill = (SKILL_DIR / "SKILL.md").read_text()
        step = skill.split("4. On goal confirmation,", 1)[1].split("\n", 1)[0]
        self.assertIn("`simulated`", step)
        self.assertNotIn("settled user decision", step)

    def test_every_copy_orders_probes_before_any_finding(self):
        flat = lambda path: " ".join(path.read_text().split())
        skill = flat(SKILL_DIR / "SKILL.md")
        # Full: the probe rule covers every message, and the "surface findings promptly" rule waits for the probes.
        self.assertRegex(skill, r"probes the user must answer when the goal is confirmed \(Session lifecycle step 4\), \*\*before\*\* any message")
        self.assertRegex(skill, r"Then put the probes to the user .* before any message shows a finding")
        self.assertRegex(skill, r"Surface material findings promptly as they arise, but only after the probes in Step 5")
        self.assertRegex(flat(SKILL_DIR / "references" / "lean-path.md"), r"ask the open probes before showing any finding")
        self.assertRegex(flat(SKILL_DIR / "references" / "agent-mode.md"), r"pre-mortem and counter-example to the operator before revealing any finding")

    def test_ledger_reference_allows_a_simulated_origin(self):
        text = " ".join((SKILL_DIR / "references" / "ledger-transitions.md").read_text().split())
        self.assertIn("`authority: user`; `simulated` in an agent-mode session", text)


if __name__ == "__main__":
    unittest.main()
