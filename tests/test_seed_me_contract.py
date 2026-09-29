"""Structural contract checks for seed-me.

These checks must not be reported as proof of transition or authorization behavior.
"""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "seed-me"


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
        self.assertIn("repository-root `seed-contract.md`", content)
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

    def test_lens_machinery_is_retired(self):
        self.assertFalse((SKILL_DIR / "references" / "epistemic-lenses.md").exists())
        content = (SKILL_DIR / "SKILL.md").read_text()
        self.assertNotIn("lens", content.lower())
        self.assertNotIn("epistemic-lenses", (ROOT / "README.md").read_text())

    def test_braindump_entry_and_draft_step(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        for required in ("braindump", "Shape the working draft",
                         "PROVISIONAL", "Only then does the frontier loop"):
            with self.subTest(required=required):
                self.assertIn(required, content)

    def test_single_presentation_template(self):
        content = (SKILL_DIR / "SKILL.md").read_text()
        self.assertEqual(len(re.findall(r"```text", content)), 1)
        self.assertIn("\U0001f4dc What I found:", content)
        self.assertIn("\U0001f464 Owner:", content)

    def test_question_format_names_options_and_assumptions(self):
        skill = (SKILL_DIR / "SKILL.md").read_text()
        ledger = (SKILL_DIR / "references/ledger-transitions.md").read_text()
        for required in ("Question 1 of 3 ready", "Option A:", "Option B:", "Undo cost:",
                         "My number to change", "Confidence:", "Would flip if:", "Not checked:", "contradicts: <node id>", "never by \"Q3\"", "You are confirming",
                         "I'll assume these unless you object", "`assumed`", "seed-contract.md",
                         "naming the three riskiest items"):
            with self.subTest(required=required):
                self.assertIn(required, skill)
        for retired in ("Decision 1 of 3 ready", "\u2753 Q1 \u2014", "pre-intent\u0060 is the handoff"):
            with self.subTest(retired=retired):
                self.assertNotIn(retired, skill)
        self.assertIn("`assumed`", ledger)
        self.assertNotIn("Decision X of Y", ledger)

    def test_size_gate_and_instinct_first(self):
        skill = (SKILL_DIR / "SKILL.md").read_text()
        lean = SKILL_DIR / "references" / "lean-path.md"
        self.assertTrue(lean.is_file())
        for required in ("Size gate", "**Lean**", "**Full**", "references/lean-path.md",
                         "Instinct first for hard-to-undo questions", "What's your instinct?",
                         "Against my suggestion:", "without `recommendation`",
                         "Ledger: <the viewer URL", "Always show where the ledger is"):
            with self.subTest(required=required):
                self.assertIn(required, skill)
        text = lean.read_text()
        for required in ("You are confirming", "status: draft | confirmed", "[evidence]",
                         "cmd: `<exact command>`", "skip the session, ledger, and viewer",
                         "print its absolute path as a `file://` link"):
            with self.subTest(lean=required):
                self.assertIn(required, text)

    def test_agent_mode_keeps_simulated_answers_apart_from_human_ones(self):
        skill = (SKILL_DIR / "SKILL.md").read_text()
        mode = SKILL_DIR / "references" / "agent-mode.md"
        self.assertTrue(mode.is_file())
        for required in ("### Agent mode (simulated operator)", "references/agent-mode.md",
                         "--operator simulated", "seed-contract.simulated.md",
                         "simulated \u2014 not confirmed by a human", "never `user` or `delegated`",
                         "scripts/engram_brief.py"):
            with self.subTest(required=required):
                self.assertIn(required, " ".join(skill.split()))
        text = mode.read_text()
        for required in ("Operator brief", "must not see", "authority: simulated",
                         "Decision style", "never authorizes implementation",
                         "engram_brief.py", "simulation, not the person", "leaves out the engram's `SKILL.md`",
                         "Large briefs.", "The operator decides; it does not build."):
            with self.subTest(mode=required):
                self.assertIn(required, text)

    def test_unknowns_are_probed_mapped_and_taught_back(self):
        skill = " ".join((SKILL_DIR / "SKILL.md").read_text().split())
        lean = (SKILL_DIR / "references" / "lean-path.md").read_text()
        for required in ("### Look for what we don't know we don't know", "Pre-mortem:", "Counter-example:",
                         "Outside view:", "Probe: <question>", "Where we did not look:", "**Knowledge map**",
                         "What we know, with proof", "What we know we don't know", "What is true but nobody has read",
                         "What could surprise us", "teach-back", "re-check trigger"):
            with self.subTest(required=required):
                self.assertIn(required, skill)
        for required in ("## Knowledge map", "Probe:", "Where we did not look:", "We would know we were wrong if:"):
            with self.subTest(lean=required):
                self.assertIn(required, lean)

    def test_lessons_from_the_engram_runs_are_in_the_skill(self):
        skill = " ".join((SKILL_DIR / "SKILL.md").read_text().split())
        mode = " ".join((SKILL_DIR / "references" / "agent-mode.md").read_text().split())
        lean = (SKILL_DIR / "references" / "lean-path.md").read_text()
        for required in ("NOT independent: asked after the finding", "Recoverability (for any decision that deletes",
                         "confirm it exists and holds what its name", "A name is a claim, not evidence",
                         "read the settled decisions against each other for contradictions",
                         "what was **decided** from what was **done**", "comes from a command, not from a summary"):
            with self.subTest(required=required):
                self.assertIn(required, skill)
        for required in ("Defer what only a person knows", "Do not hand personal file names to the operator",
                         "Check the operator's provenance claims", "Do not take its arithmetic",
                         "weak evidence", "Ask open probes first"):
            with self.subTest(mode=required):
                self.assertIn(required, mode)
        self.assertIn("recoverability probe", lean)

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
        skill = (SKILL_DIR / "SKILL.md").read_text()
        ledger = (SKILL_DIR / "references/ledger-transitions.md").read_text()
        self.assertNotIn("python3 -m http.server", skill)
        self.assertNotIn("every later node descends from it", ledger)
        for required in ('scripts/session.py" init', 'scripts/session.py" read',
                         'scripts/session.py" publish', 'scripts/session.py" end',
                         'scripts/viewer.py"', "--snapshot", "process handle",
                         "stop only the recorded viewer", "outside the repository",
                         "`seed-contract.md` is the handoff"):
            with self.subTest(required=required):
                self.assertIn(required, skill)
        for required in ("expected_version", "authority_source", "reopen_reason",
                         "helper-owned", "history", "Publication payload"):
            with self.subTest(required=required):
                self.assertIn(required, ledger)

    # docs/ chain retired with the docs tree (prune): no design docs ship;
    # runs/ carry session evidence instead.


class TestThroughlineSkillOrder(unittest.TestCase):
    def test_readme_throughline_order_and_deprecation(self):
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


if __name__ == "__main__":
    unittest.main()
