"""Activation layout: AGENTS.md routes at the published skills/ tree.

.agents/skills/ is Tink's install (gitignored), not a second source. These
checks close the two symptoms of that split:

- seed-me on the routed tree is the published skill (Seed Me title,
  assets/ledger-view.html), and a present install matches that tree.
- skill-gate is declared for install and present on the routed tree, and a
  present install contains that same tree.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_LINE = "Canonical skill tree: `skills/`"
RECEIPT = ".tink-source.json"
ROUTER_START = "<!-- AI-Native SDLC Router -->"
ROUTER_END = "<!-- End AI-Native SDLC Router -->"
CACHE_DIRS = {"__pycache__", ".git"}
CACHE_SUFFIXES = (".pyc", ".pyo", ".pyd")


def _skipped(name: str) -> bool:
    return name in CACHE_DIRS or name.endswith(CACHE_SUFFIXES)


def _canonical_mode(path: Path) -> int:
    return 0o755 if path.stat().st_mode & 0o111 else 0o644


def tree_digest_v2(root: Path, ignore=(RECEIPT,)) -> str:
    """Tink tree-digest version 2 of the published skill files.

    Python bytecode caches are omitted. They are not part of the published
    tree, and the test suite writes them beside imported scripts. Tink hashes
    whatever is on disk, so sync from a tree that still contains those caches
    will not match this pin.
    """
    entries: list[tuple[bytes, bytes, int | None, bytes | None]] = []
    ignore_set = set(ignore)
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if not _skipped(name))
        base = Path(dirpath)
        relative_dir = base.relative_to(root)
        if relative_dir != Path("."):
            entries.append((relative_dir.as_posix().encode(), b"d", None, None))
        for name in sorted(filenames):
            relative = relative_dir / name
            if relative.as_posix() in ignore_set or _skipped(name):
                continue
            file_path = base / name
            if file_path.is_symlink():
                raise AssertionError(f"symlink in skill tree: {file_path}")
            entries.append(
                (
                    relative.as_posix().encode(),
                    b"f",
                    _canonical_mode(file_path),
                    file_path.read_bytes(),
                )
            )
    entries.sort(key=lambda entry: entry[0])
    digest = hashlib.sha256()
    digest.update(b"tink-tree-digest-v2\0")
    for path, kind, mode, data in entries:
        digest.update(len(path).to_bytes(8, "big"))
        digest.update(path)
        digest.update(kind)
        if kind == b"f":
            assert mode is not None and data is not None
            digest.update(mode.to_bytes(4, "big"))
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
    return digest.hexdigest()


def _skill_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if line.strip() == "[[skills]]":
            if current:
                blocks.append(current)
            current = {}
            continue
        if line.startswith("[[") and current is not None:
            blocks.append(current)
            current = None
            continue
        if current is None or "=" not in line:
            continue
        key, value = line.split("=", 1)
        current[key.strip()] = value.strip().strip('"')
    if current:
        blocks.append(current)
    return blocks


def local_published_skills(manifest: str) -> dict[str, str]:
    found = {}
    for block in _skill_blocks(manifest):
        source = block.get("source", "")
        name = block.get("name", "")
        if name and source.startswith("skills/"):
            found[name] = source
    return found


def lock_digests(lock_text: str) -> dict[str, str]:
    found = {}
    for block in _skill_blocks(lock_text):
        name = block.get("name")
        digest = block.get("sha256")
        if name and digest:
            found[name] = digest
    return found


def _tree_records(root: Path) -> dict[str, tuple[str, int | None, bytes | None]]:
    records: dict[str, tuple[str, int | None, bytes | None]] = {}
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if not _skipped(name))
        base = Path(dirpath)
        relative_dir = base.relative_to(root)
        if relative_dir != Path("."):
            records[relative_dir.as_posix()] = ("dir", None, None)
        for name in filenames:
            relative = relative_dir / name
            if relative.as_posix() == RECEIPT or _skipped(name):
                continue
            file_path = base / name
            if file_path.is_symlink() or base.is_symlink():
                raise AssertionError(f"symlink in skill tree: {file_path}")
            records[relative.as_posix()] = (
                "file",
                _canonical_mode(file_path),
                file_path.read_bytes(),
            )
    return records


def install_delta(published: Path, installed: Path) -> list[str]:
    left = _tree_records(published)
    right = _tree_records(installed)
    delta = []
    for path in sorted(set(left) | set(right)):
        if path not in right:
            delta.append(f"missing from install: {path}")
        elif path not in left:
            delta.append(f"extra in install: {path}")
        elif left[path] != right[path]:
            delta.append(f"differs: {path}")
    return delta


class TestActivationLayout(unittest.TestCase):
    def setUp(self):
        self.agents = (ROOT / "AGENTS.md").read_text()
        self.manifest = (ROOT / ".tink" / "skills.toml").read_text()
        self.lock = (ROOT / ".tink" / "skills.lock").read_text()
        self.published = local_published_skills(self.manifest)

    def test_digest_helper_matches_tink_legacy_vector(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "resources").mkdir()
            (root / "SKILL.md").write_bytes(b"body")
            (root / "resources" / "run.sh").write_bytes(b"run")
            legacy = _legacy_digest(root)
        self.assertEqual(
            legacy,
            "f612169400ea83a502473a69fac44e95b4dff9aa49319aebc0a073b61dd57a03",
        )

    def test_agents_routes_to_published_tree(self):
        self.assertIn(CANONICAL_LINE, self.agents)
        self.assertNotIn(
            "This project uses Tink to manage Agent Skills under `.agents/skills/`.",
            self.agents,
        )
        self.assertIn("`.agents/` is installed state, not source", self.agents)
        self.assertIn("`tink skill sync`", self.agents)
        self.assertLess(
            self.agents.index(ROUTER_START),
            self.agents.index(ROUTER_END),
        )
        router_end = self.agents.index(ROUTER_END) + len(ROUTER_END)
        router = self.agents[self.agents.index(ROUTER_START) : router_end]
        self.assertIn("Read `_system/SDLC.md`", router)

    def test_issue_62_routed_seed_me_matches_published_tree(self):
        self.assertEqual(self.published["seed-me"], "skills/seed-me")
        skill_dir = ROOT / "skills" / "seed-me"
        content = (skill_dir / "SKILL.md").read_text()
        headings = re.findall(r"^#+ .+$", content, re.M)
        self.assertEqual(headings[0], "# Seed Me")
        self.assertFalse(any(re.fullmatch(r"#+ Grill Me", heading) for heading in headings))
        self.assertTrue((skill_dir / "assets" / "ledger-view.html").is_file())
        self.assertEqual(
            lock_digests(self.lock)["seed-me"],
            tree_digest_v2(skill_dir),
        )
        self._assert_install_matches("seed-me")

    def test_issue_63_skill_gate_is_on_routed_tree(self):
        self.assertEqual(self.published["skill-gate"], "skills/skill-gate")
        skill_dir = ROOT / "skills" / "skill-gate"
        content = (skill_dir / "SKILL.md").read_text()
        self.assertIn("name: skill-gate", content)
        self.assertTrue((skill_dir / "SKILL.md").is_file())
        self.assertIn("`skill-gate`", self.agents)
        self.assertEqual(
            lock_digests(self.lock)["skill-gate"],
            tree_digest_v2(skill_dir),
        )
        installed_root = ROOT / ".agents" / "skills"
        if installed_root.exists():
            self.assertTrue(
                (installed_root / "skill-gate" / "SKILL.md").is_file(),
                "skill-gate is declared in .tink/skills.toml but missing from "
                ".agents/skills/. Run tink skill sync. If sync refuses an "
                "existing skill, remove that .agents/skills/<name> directory "
                "and rerun sync.",
            )
        self._assert_install_matches("skill-gate")

    def test_local_lock_pins_match_published_trees(self):
        digests = lock_digests(self.lock)
        for name, source in sorted(self.published.items()):
            with self.subTest(skill=name):
                self.assertEqual(
                    digests[name],
                    tree_digest_v2(ROOT / source),
                    f"update .tink/skills.lock sha256 for {name} to the "
                    "published tree digest so tink skill sync can install it",
                )

    def _assert_install_matches(self, name: str):
        installed = ROOT / ".agents" / "skills" / name
        if not installed.exists():
            return
        published = ROOT / self.published[name]
        delta = install_delta(published, installed)
        self.assertEqual(
            delta,
            [],
            f".agents/skills/{name} drifted from {self.published[name]}:\n"
            + "\n".join(delta),
        )


def _legacy_digest(root: Path) -> str:
    entries: list[tuple[bytes, bytes, bytes | None]] = []
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(dirnames)
        base = Path(dirpath)
        relative_dir = base.relative_to(root)
        if relative_dir != Path("."):
            entries.append((relative_dir.as_posix().encode(), b"d", None))
        for name in sorted(filenames):
            relative = relative_dir / name
            data = (base / name).read_bytes()
            entries.append((relative.as_posix().encode(), b"f", data))
    entries.sort(key=lambda entry: entry[0])
    digest = hashlib.sha256()
    for path, kind, data in entries:
        digest.update(len(path).to_bytes(8, "big"))
        digest.update(path)
        digest.update(kind)
        if kind == b"f":
            assert data is not None
            digest.update(len(data).to_bytes(8, "big"))
            digest.update(data)
    return digest.hexdigest()


if __name__ == "__main__":
    unittest.main()
