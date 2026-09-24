import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'skills/ai-native-sdlc/assets/_system/scripts/sdlc.py'
spec = importlib.util.spec_from_file_location('workflow', SOURCE)
workflow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        shutil.copytree(SOURCE.parents[2] / '_shared', self.root / '_shared')
        (self.root / '_system/scripts').mkdir(parents=True)
        shutil.copyfile(SOURCE, self.root / '_system/scripts/sdlc.py')
        (self.root / 'stages/01-plan').mkdir(parents=True)
        (self.root / 'stages/01-plan/CONTEXT.md').write_text('contract')
        (self.root / 'code.py').write_text('original')
        self.config([{'argv': ['python3', '-c', 'print("real check")'], 'timeout_seconds': 5}])
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@local', 'commit', '-qm', 'baseline')

    def git(self, *args):
        subprocess.run(['git', '-C', str(self.root), *args], check=True, capture_output=True)

    def config(self, checks, require_tink=False):
        (self.root / '_system/verification.json').write_text(json.dumps({'checks': checks, 'require_tink': require_tink}))

    def cli(self, *args, ok=True):
        result = subprocess.run(['python3', str(self.root / '_system/scripts/sdlc.py'), *args], cwd='/', capture_output=True, text=True)
        self.assertEqual(result.returncode == 0, ok, result.stdout + result.stderr)
        return result.stdout + result.stderr

    def approve(self, stage='3'):
        self.cli('decide', 'example', stage, 'approved', '--reviewer', 'human', '--source', 'review:1', '--reason', 'accepted')

    def create_ready(self, *args):
        self.cli('new', 'example', *args)
        self.approve()

    def test_slug_and_no_overwrite(self):
        self.cli('new', '../escape', ok=False)
        self.cli('new', 'example')
        brief = self.root / 'runs/example/brief.md'
        brief.write_text('human work')
        self.cli('new', 'example', ok=False)
        self.assertEqual(brief.read_text(), 'human work')

    def test_concurrent_creation(self):
        command = ['python3', str(self.root / '_system/scripts/sdlc.py'), 'new', 'race']
        a = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        b = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        a.communicate(); b.communicate()
        self.assertEqual(sorted([a.returncode, b.returncode]), [0, 1])
        self.assertTrue((self.root / 'runs/race/run.json').exists())

    def test_text_is_not_approval_or_verification(self):
        self.cli('new', 'example')
        (self.root / 'runs/example/brief.md').write_text('**Status:** approved')
        directory = self.root / 'runs/example/04-test/output'
        directory.mkdir(parents=True)
        (directory / 'test-log.md').write_text('all passed')
        out = self.cli('status', 'example')
        self.assertIn('Stage 3: pending', out)
        self.assertIn('Verification: not run (implementation may be pending; a text log is not passing evidence)', out)
        self.cli('verify', 'example', ok=False)

    def test_verification_wrapper_requires_run_id(self):
        wrapper = self.root / '_system/scripts/verify.sh'
        wrapper.write_text(
            '#!/usr/bin/env bash\n'
            'set -euo pipefail\n'
            'SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"\n'
            'if [ "$#" -ne 1 ]; then\n'
            '  echo "Usage: $0 <run-id>" >&2\n'
            '  echo "Create a run first with: ${SCRIPT_DIR}/new-run.sh <run-id>" >&2\n'
            '  exit 2\n'
            'fi\n'
            'exec python3 "${SCRIPT_DIR}/sdlc.py" verify "$@"\n'
        )
        wrapper.chmod(0o755)
        result = subprocess.run(['bash', str(wrapper)], cwd='/', capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Usage:', result.stderr)
        self.assertIn('new-run.sh', result.stderr)

    def test_stale_approval_and_rejection(self):
        self.create_ready()
        (self.root / 'runs/example/brief.md').write_text('new requirements')
        self.assertIn('Stage 3: stale', self.cli('status', 'example'))
        self.approve()
        self.cli('decide', 'example', '3', 'changes-requested', '--reviewer', 'human', '--source', 'review:2', '--reason', 'scope')
        self.assertIn('changes-requested', self.cli('status', 'example'))
        self.cli('verify', 'example', ok=False)

    def test_full_dependency_chain(self):
        self.cli('new', 'example', '--profile', 'full')
        self.cli('decide', 'example', '2', 'approved', '--reviewer', 'human', '--source', 'review:1', '--reason', 'yes', ok=False)
        for stage in ['1', '2', '3']:
            self.approve(stage)
        (self.root / 'runs/example/01-plan/output/intent.md').write_text('changed intent')
        out = self.cli('status', 'example')
        self.assertIn('Stage 2: stale', out)
        self.assertIn('Stage 3: stale', out)

    def test_evidence_bound_to_code_and_log(self):
        self.create_ready()
        self.cli('verify', 'example')
        self.assertIn('Verification: current', self.cli('status', 'example'))
        (self.root / 'code.py').write_text('different')
        self.assertIn('stale', self.cli('status', 'example'))
        self.cli('verify', 'example')
        (self.root / 'runs/example/04-test/output/test-log.md').write_text('edited')
        self.assertIn('stale', self.cli('status', 'example'))

    def test_untracked_python_cache_does_not_fail_passing_suite(self):
        self.create_ready()
        (self.root / 'tests').mkdir()
        (self.root / 'tests/test_real.py').write_text('import unittest\nclass Check(unittest.TestCase):\n def test_ok(self): self.assertEqual(2 + 2, 4)\n')
        self.config([{'argv': ['python3', '-m', 'unittest', 'discover', '-s', 'tests'], 'timeout_seconds': 5}])
        self.cli('verify', 'example')
        self.assertTrue(list((self.root / 'tests/__pycache__').glob('*.pyc')))
        self.assertIn('Verification: current', self.cli('status', 'example'))

    def test_tracked_cache_remains_covered(self):
        self.create_ready()
        (self.root / 'tracked.pyc').write_bytes(b'original')
        self.git('add', 'tracked.pyc')
        self.cli('verify', 'example')
        (self.root / 'tracked.pyc').write_bytes(b'changed')
        self.assertIn('stale', self.cli('status', 'example'))

    def test_evidence_commit_preserves_content_verification(self):
        self.create_ready()
        self.cli('verify', 'example')
        self.git('add', 'runs')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@local', 'commit', '-qm', 'record evidence')
        self.assertIn('Verification: current', self.cli('status', 'example'))
        (self.root / 'code.py').write_text('changed source')
        self.git('add', 'code.py')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@local', 'commit', '-qm', 'change source')
        self.assertIn('stale', self.cli('status', 'example'))

    def test_missing_empty_failed_and_timeout_checks(self):
        self.create_ready()
        for checks in [[], [{'argv': ['missing-executable-sdlc'], 'timeout_seconds': 1}],
                       [{'argv': ['python3', '-c', 'raise SystemExit(1)'], 'timeout_seconds': 1}],
                       [{'argv': ['python3', '-c', 'import time; time.sleep(3)'], 'timeout_seconds': 1}]]:
            self.config(checks)
            self.cli('verify', 'example', ok=False)
            self.assertNotIn('Verification: current', self.cli('status', 'example'))

    def test_required_tink_is_not_optional(self):
        self.create_ready()
        self.config([{'argv': ['true'], 'timeout_seconds': 1}], True)
        original_run = workflow.subprocess.run
        def missing_tink(argv, **kwargs):
            if argv[0] == 'tink':
                raise FileNotFoundError('tink unavailable')
            return original_run(argv, **kwargs)
        with patch.object(workflow, 'ROOT', self.root), patch.object(workflow.subprocess, 'run', side_effect=missing_tink):
            with self.assertRaises(FileNotFoundError):
                workflow.verify(SimpleNamespace(run='example'))
        receipt = json.loads((self.root / 'runs/example/04-test/output/verification.json').read_text())
        self.assertEqual(receipt['result'], 'failed')

    def test_skill_wrapper_lock_and_symlink(self):
        args = SimpleNamespace(tool='tink', arguments=['skill', 'check'])
        with patch.object(workflow, 'ROOT', self.root), patch.object(workflow.tempfile, 'gettempdir', return_value=str(self.root)):
            lock = self.root / f'sdlc-tink-{workflow.os.getuid()}.lock'
            lock.mkdir()
            with self.assertRaises(ValueError):
                workflow.skills(args)
            lock.rmdir()
            (self.root / '.agents').symlink_to(self.root, target_is_directory=True)
            with self.assertRaises(ValueError):
                workflow.skills(args)

    def test_candidate_mutation_during_check(self):
        self.create_ready()
        self.config([{'argv': ['python3', '-c', 'from pathlib import Path; Path("code.py").write_text("modified")'], 'timeout_seconds': 2}])
        self.assertIn('changed during verification', self.cli('verify', 'example', ok=False))

    def test_bug_requires_unchanged_test_baseline(self):
        self.create_ready('--kind', 'bug')
        self.cli('verify', 'example', ok=False)
        (self.root / 'regression.py').write_text('assert True')
        self.cli('lock-tests', 'example', 'regression.py', '--source', 'review:3', '--failure-evidence', 'ci:failed-reproduction')
        self.cli('verify', 'example')
        (self.root / 'regression.py').write_text('weakened')
        self.cli('verify', 'example', ok=False)

    def test_symlink_run_rejected(self):
        (self.root / 'runs').mkdir()
        (self.root / 'runs/link').symlink_to(self.root, target_is_directory=True)
        self.cli('status', 'link', ok=False)


if __name__ == '__main__':
    unittest.main()
