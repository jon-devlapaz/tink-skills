import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/ai-native-sdlc'
SPEC = importlib.util.spec_from_file_location('bootstrap', SKILL / 'scripts/init.py')
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


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

    def test_ordinary_write_error_rolls_back(self):
        original = Path.open
        calls = 0
        def failing_open(path, mode='r', *args, **kwargs):
            nonlocal calls
            if mode == 'xb':
                calls += 1
                if calls == 3:
                    raise OSError('injected write error')
            return original(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', failing_open):
            with self.assertRaisesRegex(OSError, 'injected'):
                bootstrap.install(self.root)
        self.assertEqual(self.contents(), {})
        self.run_init()

    def test_generated_package_matches_sources(self):
        result = subprocess.run(['python3', str(SKILL / 'scripts/package.py'), '--check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_agents_write_failure_restores_original(self):
        (self.root / 'AGENTS.md').write_text('Existing instructions')
        original = (self.root / 'AGENTS.md').read_bytes()
        real_write_bytes = Path.write_bytes
        calls = []
        def failing_write(path, data, *args, **kwargs):
            if not calls:
                calls.append(path)
                real_write_bytes(path, b'PARTIAL-')
                raise OSError('injected AGENTS write error')
            return real_write_bytes(path, data, *args, **kwargs)
        with patch.object(Path, 'write_bytes', failing_write):
            with self.assertRaisesRegex(OSError, 'injected AGENTS write error'):
                bootstrap.install(self.root)
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), original)
        self.assertFalse((self.root / '.AGENTS.md.sdlc-install-tmp').exists())
        self.assertFalse((self.root / '_system').exists())
        self.assertFalse((self.root / 'stages').exists())
        self.assertFalse((self.root / '_shared').exists())
        self.assertFalse((self.root / '.sdlc-init-lock').exists())
        self.run_init()

    def test_agents_write_failure_without_original_leaves_no_agents_file(self):
        real_write_bytes = Path.write_bytes
        calls = []
        def failing_write(path, data, *args, **kwargs):
            if not calls:
                calls.append(path)
                real_write_bytes(path, b'PARTIAL-')
                raise OSError('injected AGENTS write error')
            return real_write_bytes(path, data, *args, **kwargs)
        with patch.object(Path, 'write_bytes', failing_write):
            with self.assertRaisesRegex(OSError, 'injected AGENTS write error'):
                bootstrap.install(self.root)
        self.assertFalse((self.root / 'AGENTS.md').exists())
        self.assertFalse((self.root / '.AGENTS.md.sdlc-install-tmp').exists())
        self.assertFalse((self.root / '_system').exists())
        self.assertFalse((self.root / '.sdlc-init-lock').exists())
        self.run_init()

    def test_receipt_failure_restores_agents_and_scaffold(self):
        (self.root / 'AGENTS.md').write_text('keep me')
        real_open = Path.open
        def failing_open(path, mode='r', *args, **kwargs):
            if path.name == 'scaffold.json' and mode == 'x':
                raise OSError('injected receipt error')
            return real_open(path, mode, *args, **kwargs)
        with patch.object(Path, 'open', failing_open):
            with self.assertRaisesRegex(OSError, 'injected receipt error'):
                bootstrap.install(self.root)
        self.assertEqual((self.root / 'AGENTS.md').read_text(), 'keep me')
        self.assertFalse((self.root / '_system').exists())
        self.assertFalse((self.root / 'stages').exists())
        self.assertFalse((self.root / '_shared').exists())
        self.assertFalse((self.root / '.sdlc-init-lock').exists())
        self.run_init()

    def test_rollback_cleanup_failure_preserves_original_error(self):
        (self.root / 'AGENTS.md').write_text('keep me')
        real_open = Path.open
        state = {'calls': 0}
        def failing_open(path, mode='r', *args, **kwargs):
            if mode == 'xb':
                state['calls'] += 1
                if state['calls'] == 2:
                    raise OSError('original write error')
            return real_open(path, mode, *args, **kwargs)
        def failing_unlink(path, *args, **kwargs):
            raise OSError('injected cleanup error')
        with patch.object(Path, 'open', failing_open), patch.object(Path, 'unlink', failing_unlink):
            with self.assertRaises(RuntimeError) as ctx:
                bootstrap.install(self.root)
        self.assertIn('original write error', str(ctx.exception))
        self.assertIn('injected cleanup error', str(ctx.exception))
        self.assertIsInstance(ctx.exception.__cause__, OSError)

    def test_lock_cleanup_failure_on_success_surfaced(self):
        real_rmdir = Path.rmdir
        def failing_rmdir(path, *args, **kwargs):
            if path.name == '.sdlc-init-lock':
                raise OSError('injected lock cleanup error')
            return real_rmdir(path, *args, **kwargs)
        with patch.object(Path, 'rmdir', failing_rmdir):
            with self.assertRaisesRegex(RuntimeError, 'lock cleanup failed'):
                bootstrap.install(self.root)
        self.assertTrue((self.root / '_system/SDLC.md').is_file())
        self.assertTrue((self.root / '.sdlc-init-lock').exists())

    def test_lock_cleanup_failure_on_error_reports_both(self):
        real_open = Path.open
        state = {'calls': 0}
        def failing_open(path, mode='r', *args, **kwargs):
            if mode == 'xb':
                state['calls'] += 1
                if state['calls'] == 2:
                    raise OSError('original write error')
            return real_open(path, mode, *args, **kwargs)
        real_rmdir = Path.rmdir
        def failing_rmdir(path, *args, **kwargs):
            if path.name == '.sdlc-init-lock':
                raise OSError('injected lock cleanup error')
            return real_rmdir(path, *args, **kwargs)
        with patch.object(Path, 'open', failing_open), patch.object(Path, 'rmdir', failing_rmdir):
            with self.assertRaises(RuntimeError) as ctx:
                bootstrap.install(self.root)
        self.assertIn('original write error', str(ctx.exception))
        self.assertIn('lock cleanup', str(ctx.exception))

    def test_concurrent_agents_change_aborts_without_overwrite(self):
        (self.root / 'AGENTS.md').write_text('v1 instructions')
        real_read_bytes = Path.read_bytes
        state = {'calls': 0}
        def concurrent_read(path, *args, **kwargs):
            data = real_read_bytes(path, *args, **kwargs)
            if path.name == 'AGENTS.md':
                state['calls'] += 1
                if state['calls'] == 2:
                    Path.write_bytes(path, b'v2 concurrent edit')
                    return real_read_bytes(path, *args, **kwargs)
            return data
        with patch.object(Path, 'read_bytes', concurrent_read):
            with self.assertRaisesRegex(ValueError, 'changed during initialization'):
                bootstrap.install(self.root)
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), b'v2 concurrent edit')
        self.assertFalse((self.root / '_system').exists())
        self.assertFalse((self.root / '.sdlc-init-lock').exists())

    def test_install_preserves_agents_file_mode(self):
        agents = self.root / 'AGENTS.md'
        agents.write_text('Existing instructions')
        agents.chmod(0o600)
        self.run_init()
        self.assertTrue(agents.read_text().startswith('Existing instructions'))
        self.assertEqual(agents.stat().st_mode & 0o777, 0o600)

    def test_main_reports_runtime_error_without_traceback(self):
        with patch.object(bootstrap, 'install', side_effect=RuntimeError('injected rollback error')):
            with patch.object(bootstrap.sys, 'argv', ['init.py', str(self.root)]):
                with patch.object(bootstrap.sys, 'stderr') as stderr:
                    self.assertEqual(bootstrap.main(), 1)
        combined = ''.join(call[0][0] for call in stderr.write.call_args_list)
        self.assertIn('injected rollback error', combined)

    def test_stale_installer_tmp_file_refused(self):
        tmp = self.root / '.AGENTS.md.sdlc-install-tmp'
        tmp.write_bytes(b'user data')
        self.run_init(ok=False)
        self.assertEqual(tmp.read_bytes(), b'user data')
        self.assertFalse((self.root / '_system').exists())


if __name__ == '__main__':
    unittest.main()
