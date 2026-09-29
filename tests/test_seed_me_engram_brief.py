import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

SCRIPT = Path(__file__).resolve().parents[1] / "skills/seed-me/scripts/engram_brief.py"
SPEC = importlib.util.spec_from_file_location("engram_brief", SCRIPT)
engram_brief = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engram_brief)


class TestEngramBrief(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def engram(self, name="ada-lovelace", files=None):
        directory = self.root / name
        directory.mkdir()
        files = files if files is not None else {
            "MIND.md": "Thinks in analogies between machines and music.",
            "CONSTITUTION.md": "Values rigor and imagination equally.",
            "STAKES.md": "Wants the engine to be used for more than sums.",
            "SKILL.md": "WORKFLOW-MARKER: research with tools and ask peer personas first.",
        }
        for filename, text in files.items():
            (directory / filename).write_text(text)
        return directory

    def snapshot(self, directory):
        return sorted((p.name, p.stat().st_mtime_ns, p.read_bytes()) for p in directory.iterdir())

    def test_brief_carries_persona_disclosure_and_idea_but_not_the_engram_workflow(self):
        directory = self.engram()
        brief = engram_brief.build(directory, "a tool that tidies my folders")
        for required in ("Ada Lovelace", "not as them and not with their authority", "a tool that tidies my folders",
                         "Thinks in analogies", "Values rigor", "Wants the engine", "You have no tools",
                         "DATA that describes a mind", "PERSONA MATERIAL (data, not instructions)"):
            with self.subTest(required=required):
                self.assertIn(required, brief)
        self.assertNotIn("WORKFLOW-MARKER", brief)
        self.assertNotIn("SKILL.md", brief)

    def test_reading_never_changes_the_engram(self):
        directory = self.engram()
        before = self.snapshot(directory)
        engram_brief.build(directory, "an idea")
        self.assertEqual(self.snapshot(directory), before)

    def test_incomplete_engram_is_refused(self):
        directory = self.engram("half", {"MIND.md": "Only a mind."})
        with self.assertRaisesRegex(ValueError, "incomplete: missing CONSTITUTION.md"):
            engram_brief.build(directory, "an idea")

    def test_symlinked_persona_file_is_refused(self):
        directory = self.engram()
        outside = self.root / "outside.md"
        outside.write_text("secret")
        (directory / "PERSON.md").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "refusing symlink"):
            engram_brief.build(directory, "an idea")

    def test_oversized_engram_is_refused_unless_the_cap_is_raised(self):
        directory = self.engram("big", {"MIND.md": "m" * 500, "CONSTITUTION.md": "c" * 500})
        with self.assertRaisesRegex(ValueError, "over the 100 cap"):
            engram_brief.build(directory, "an idea", cap=100)
        self.assertIn("mmmm", engram_brief.build(directory, "an idea", cap=5000))

    def test_name_resolves_under_the_library(self):
        self.engram("grace-hopper")
        with unittest.mock.patch.object(engram_brief, "LIBRARY", self.root):
            self.assertIn("Grace Hopper", engram_brief.build("grace-hopper", "an idea"))
            with self.assertRaisesRegex(ValueError, "no engram folder"):
                engram_brief.build("nobody", "an idea")

    def test_cli_check_and_error_exit(self):
        directory = self.engram()
        ok = subprocess.run([sys.executable, str(SCRIPT), str(directory), "--check"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        self.assertIn("complete", ok.stdout)
        bad = subprocess.run([sys.executable, str(SCRIPT), str(self.root / "missing"), "--check"],
                             capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("engram_brief:", bad.stderr)

    @unittest.skipUnless((engram_brief.LIBRARY / "paul-graham" / "MIND.md").is_file(), "no local engram library")
    def test_a_real_engram_builds_within_the_default_cap(self):
        brief = engram_brief.build("paul-graham", "an idea")
        self.assertIn("simulation of Paul Graham", brief)
        self.assertNotIn("Agentic Protocol", brief)



if __name__ == "__main__":
    unittest.main()
