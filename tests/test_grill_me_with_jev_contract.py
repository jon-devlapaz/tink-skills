"""Structural contract checks for grill-me-with-jev.

These checks must not be reported as proof of transition or authorization behavior.
"""

from pathlib import Path
import re
import unittest
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "grill-me-with-jev"


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
        for ref_name in ("ledger-transitions.md", "typesafe-protocol.md"):
            with self.subTest(ref=ref_name):
                self.assertIn(SKILL_DIR / "references" / ref_name, links)

    def test_artifact_chain_relative_links_resolve(self):
        checked = 0
        for folder, artifact in (("intent", "intent"), ("specs", "spec"),
                                 ("plans", "plan"), ("reviews", "review")):
            path = ROOT / "docs" / folder / f"grill-me-with-jev-{artifact}.md"
            if not path.is_file():
                continue
            checked += 1
            for href in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
                if "://" in href or href.startswith(("/", "#")):
                    continue
                target = (path.parent / href.split("#")[0]).resolve()
                if not target.is_file() and ("grill-me-with-jev-intent.md" in href or "evals" in href):
                    continue
                self.assertTrue(target.is_file(), href)
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
