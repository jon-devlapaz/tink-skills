"""Contract tests for Skill Scout's read-only candidate inspection boundary."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / "skills" / "skill-scout" / "references" / "scouting-workflow.md"
INSPECTION = REPO_ROOT / "skills" / "skill-scout" / "references" / "repository-inspection.md"
MALICIOUS_CANDIDATE = REPO_ROOT / "tests" / "fixtures" / "skill-scout-malicious-candidate"
AUDIT = REPO_ROOT / "skills" / "skill-eval-loop" / "scripts" / "audit_suite.py"


class SkillScoutContractTests(unittest.TestCase):
    def test_published_eval_suite_proves_every_case_contrast(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(AUDIT),
                "--skill-path",
                str(REPO_ROOT / "skills" / "skill-scout"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        self.assertTrue(report["valid"])
        self.assertEqual(report["grader_discrimination"]["claim"], "case_contrast")
        self.assertEqual(
            report["grader_discrimination"]["contrast_case_count"],
            report["case_count"],
        )
        self.assertGreater(
            report["grader_discrimination"]["deterministic_graders_checked"],
            0,
        )

    def test_candidate_helpers_are_inert_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "executed"
            with patch.dict(os.environ, {"SKILL_SCOUT_EXECUTION_MARKER": str(marker)}):
                workflow = WORKFLOW.read_text()
                helper = (MALICIOUS_CANDIDATE / "repo-brief" / "scripts" / "repo_brief.mjs").read_text()

        self.assertIn("writeFileSync", helper)
        self.assertFalse(marker.exists(), "candidate-owned helper was executed")
        self.assertIn("repository-inspection.md", workflow)

    def test_repository_inspection_contract_is_inert_and_complete(self) -> None:
        skill = (REPO_ROOT / "skills" / "skill-scout" / "SKILL.md").read_text()
        workflow = WORKFLOW.read_text()
        inspection = INSPECTION.read_text()
        published_contract = skill + workflow + inspection

        for required in (
            "exact revision",
            "Inventory",
            "Indicators",
            "Citations",
            "Unknowns",
            "Limitations",
            "Never execute candidate-provided",
        ):
            self.assertIn(required, inspection)
        self.assertIn("repository-inspection.md", skill)
        self.assertNotIn("repo-brief", published_contract.lower())
        self.assertNotIn("repo_brief", published_contract.lower())


if __name__ == "__main__":
    unittest.main()
