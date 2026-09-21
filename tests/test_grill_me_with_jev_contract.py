"""Structural checks only; agent behavior is evaluated with evals/evals.json.

These checks must not be reported as proof of transition or authorization behavior.
"""

import ast
import json
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
        self.assertIn(SKILL_DIR / "references" / "triage-patterns.md", links)

    def test_eval_cases_are_unique_and_actionable(self):
        suite = json.loads((SKILL_DIR / "evals" / "evals.json").read_text())
        self.assertEqual(suite["skill"], SKILL_DIR.name)
        self.assertTrue(suite["protocol"].strip())
        cases = suite["cases"]
        self.assertTrue(cases)
        self.assertEqual(len(cases), len({case["id"] for case in cases}))
        for case in cases:
            with self.subTest(case=case["id"]):
                self.assertRegex(case["id"], r"^[a-z][a-z0-9-]+$")
                self.assertTrue(case["input"].strip())
                self.assertTrue(case["expected"])
                self.assertTrue(all(isinstance(item, str) and item.strip()
                                    for item in case["expected"]))
                self.assertTrue(case["requirements"])

    def test_every_requirement_has_an_eval(self):
        spec = (ROOT / "docs/specs/grill-me-with-jev-spec.md").read_text()
        requirements = set(re.findall(r"^\| (R\d+) \|", spec, re.MULTILINE))
        self.assertTrue(requirements)
        suite = json.loads((SKILL_DIR / "evals/evals.json").read_text())
        covered = {requirement for case in suite["cases"]
                   for requirement in case["requirements"]}
        self.assertEqual(requirements, covered)

    def test_service_fixture_is_valid_readable_python(self):
        fixture = SKILL_DIR / "evals/fixture/service.py"
        tree = ast.parse(fixture.read_text(), filename=str(fixture))
        self.assertTrue(tree.body)

    def test_artifact_chain_relative_links_resolve(self):
        for folder, artifact in (("intent", "intent"), ("specs", "spec"),
                                 ("plans", "plan"), ("reviews", "review")):
            path = ROOT / "docs" / folder / f"grill-me-with-jev-{artifact}.md"
            self.assertTrue(path.is_file(), path)
            for href in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
                if "://" in href or href.startswith(("/", "#")):
                    continue
                self.assertTrue((path.parent / href.split("#")[0]).resolve().is_file(), href)


if __name__ == "__main__":
    unittest.main()
