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
    def test_operational_references_resolve_inside_skill(self):
        for path in SKILL_DIR.rglob("*.md"):
            for href in re.findall(r"\[[^\]]*\]\(([^)]+)\)", path.read_text()):
                if "://" in href or href.startswith("#"):
                    continue
                target = (path.parent / unquote(href.split("#")[0])).resolve()
                self.assertTrue(target.is_relative_to(SKILL_DIR.resolve()), target)
                self.assertTrue(target.is_file(), target)


class TestThroughlineSkillOrder(unittest.TestCase):
    def test_grill_me_with_jev_is_removed(self):
        self.assertFalse((ROOT / "skills" / "grill-me-with-jev").exists())


if __name__ == "__main__":
    unittest.main()
