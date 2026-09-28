"""Eval-contract convention checks for seed-me (salvaged from agentic-se-skills).

Encodes the eval file contract without requiring evals to exist yet.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "seed-me"
MODULE_PATH = SKILL_DIR / "references" / "nasa-spike" / "run_eval_contracts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("seed_me_run_eval_contracts", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSeedMeEvalContracts(unittest.TestCase):
    def test_required_fields_present(self):
        module = load_module()
        for field in (
            "Scenario",
            "Skill under test",
            "Input prompt",
            "Expected artifacts",
            "Pass criteria",
            "Failure signals",
            "Scoring rubric",
        ):
            self.assertIn(field, module.REQUIRED_FIELDS)

    def test_empty_dir_reports_no_evals(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(module.check_eval_contracts(Path(tmp)), ["no eval markdown files found"])

    def test_valid_eval_passes(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            evals = Path(tmp) / "evals"
            evals.mkdir()
            (evals / "sample.md").write_text(
                "## Scenario\ns\n## Skill under test\nseed-me\n## Input prompt\ni\n"
                "## Expected artifacts\ne\n## Pass criteria\np\n## Failure signals\nf\n"
                "## Scoring rubric\nr\n"
            )
            self.assertEqual(module.check_eval_contracts(Path(tmp)), [])


if __name__ == "__main__":
    unittest.main()
