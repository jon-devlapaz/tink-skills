import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ai-native-sdlc'


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def run_init(self, *args, ok=True):
        result = subprocess.run(['python3', str(SKILL / 'scripts/init.py'), str(self.root), *args], capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result

    def contents(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_fresh_install_complete_and_unconfigured(self):
        (self.root / 'README.md').write_text('Product documentation')
        (self.root / 'AGENTS.md').write_text('Existing instructions')
        self.run_init()
        self.assertEqual((self.root / 'README.md').read_text(), 'Product documentation')
        self.assertTrue((self.root / 'AGENTS.md').read_text().startswith('Existing instructions'))
        self.assertTrue((self.root / '_system/SDLC.md').is_file())
        self.assertEqual(json.loads((self.root / '_system/verification.json').read_text())['checks'], [])
        for path in (self.root / 'stages').rglob('*.md'):
            self.assertNotIn('`README.md`', path.read_text())
        spec = importlib.util.spec_from_file_location('installed_workflow', self.root / '_system/scripts/sdlc.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(ValueError, 'nonempty check list'):
            module.checks_config()
        result = subprocess.run(['bash', str(self.root / '_system/scripts/new-run.sh'), 'probe'], cwd='/', capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / 'runs/probe/brief.md').is_file())

    def test_preview_does_not_write(self):
        self.run_init('--check')
        self.assertEqual(list(self.root.iterdir()), [])

    def test_repeat_preserves_config_and_active_run(self):
        self.run_init()
        config = self.root / '_system/verification.json'
        config.write_text(json.dumps({'require_tink': True, 'checks': [{'argv': ['custom'], 'timeout_seconds': 10}]}))
        (self.root / 'runs/active').mkdir(parents=True)
        before = self.contents()
        self.run_init()
        self.assertEqual(before, self.contents())

    def test_customized_managed_file_refused_without_changes(self):
        self.run_init()
        (self.root / 'stages/03-build/CONTEXT.md').write_text('custom policy')
        before = self.contents()
        self.run_init(ok=False)
        self.assertEqual(before, self.contents())

    def test_unmanaged_collision_preflight(self):
        (self.root / '_shared').mkdir()
        (self.root / '_shared/REVIEW.md').write_text('custom')
        before = self.contents()
        self.run_init(ok=False)
        self.assertEqual(before, self.contents())

    def test_upgrade_refused(self):
        self.run_init()
        path = self.root / '_system/scaffold.json'
        data = json.loads(path.read_text()); data['version'] = 'old'
        path.write_text(json.dumps(data))
        before = self.contents()
        self.run_init(ok=False)
        self.assertEqual(before, self.contents())

    def test_symlink_destination_refused(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.root / '_shared').symlink_to(outside)
            self.run_init(ok=False)
            self.assertEqual(list(Path(outside).iterdir()), [])

    def test_active_unmanaged_run_refused(self):
        (self.root / 'runs/active').mkdir(parents=True)
        self.run_init(ok=False)
        self.assertFalse((self.root / '_system').exists())

    def test_missing_file_refused(self):
        self.run_init()
        (self.root / '_system/scripts/status.sh').unlink()
        self.run_init(ok=False)
        self.assertFalse((self.root / '_system/scripts/status.sh').exists())

    def test_force_not_supported(self):
        self.run_init('--force', ok=False)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_generated_package_matches_sources(self):
        result = subprocess.run(['python3', str(SKILL / 'scripts/package.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_install_preserves_agents_file_mode(self):
        agents = self.root / 'AGENTS.md'
        agents.write_text('Existing instructions')
        agents.chmod(0o600)
        self.run_init()
        self.assertTrue(agents.read_text().startswith('Existing instructions'))
        self.assertEqual(agents.stat().st_mode & 0o777, 0o600)

    def test_stale_installer_tmp_file_refused(self):
        tmp = self.root / '.AGENTS.md.sdlc-install-tmp'
        tmp.write_bytes(b'user data')
        self.run_init(ok=False)
        self.assertEqual(tmp.read_bytes(), b'user data')
        self.assertFalse((self.root / '_system').exists())


if __name__ == '__main__':
    unittest.main()
