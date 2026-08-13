"""Contract tests for the published Triangulate evaluation suite."""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL = REPO_ROOT / "skills" / "triangulate-me"
AUDIT = REPO_ROOT / "skills" / "skill-eval-loop" / "scripts" / "audit_suite.py"


class TriangulateEvalContractTests(unittest.TestCase):
    def test_pricing_case_is_provenanced_and_contrast_covered(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(AUDIT), "--skill-path", str(SKILL)],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        suite = json.loads((SKILL / "evals" / "evals.json").read_text())
        case_ids = {case["id"] for case in suite["evals"]}

        self.assertTrue(report["valid"])
        self.assertIn("separates-headline-price-from-contractual-cost", case_ids)
        self.assertEqual(
            report["grader_discrimination"]["contrast_case_count"],
            report["case_count"],
        )
        self.assertEqual(report["provenance_case_count"], report["case_count"])


if __name__ == "__main__":
    unittest.main()
