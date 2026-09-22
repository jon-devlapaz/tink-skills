#!/usr/bin/env python3
"""Install a versioned SDLC scaffold. Existing installations are checked, never upgraded."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1] / 'assets'
RECEIPT = '_system/scaffold.json'
CONFIG = '_system/verification.json'
ROUTER = '''<!-- AI-Native SDLC Router -->
## SDLC Workspace
- Read `_system/SDLC.md` for setup, evidence boundaries, and recovery.
- Inspect `_system/scripts/status.sh` before creating a run.
- Read `stages/<stage-name>/CONTEXT.md` before processing a stage.
- Keep factory references in `_shared/` unchanged during feature runs.
- Use separate worktrees or clones for code-writing runs.
<!-- End AI-Native SDLC Router -->'''


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe(root, relative):
    part = Path(relative)
    if part.is_absolute() or '..' in part.parts:
        raise ValueError(f'Invalid package path: {relative}')
    target = root / part
    if target.resolve() != target.absolute():
        raise ValueError(f'Symlink destination refused: {relative}')
    for parent in target.parents:
        if parent == root:
            break
        if parent.exists() and not parent.is_dir():
            raise ValueError(f'Parent is not a directory: {parent}')
    return target


def package_files():
    manifest = json.loads((PACKAGE / 'manifest.json').read_text())
    files = {}
    for relative, expected in manifest['files'].items():
        data = safe(PACKAGE, relative).read_bytes()
        if sha(data) != expected:
            raise ValueError(f'Package integrity mismatch: {relative}')
        files[relative] = data
    return manifest, files


def install(root, check=False):
    root = root.resolve()
    if not root.is_dir():
        raise ValueError('Target must be an existing project directory.')
    lock = root / '.sdlc-init-lock'
    try:
        lock.mkdir()
    except FileExistsError:
        raise ValueError('Initialization busy or interrupted; confirm no initializer remains before removing .sdlc-init-lock.')
    try:
        manifest, files = package_files()
        receipt = safe(root, RECEIPT)
        agents = safe(root, 'AGENTS.md')
        original = agents.read_bytes() if agents.exists() else None
        agents_mode = agents.stat().st_mode if original is not None else None
        tmp_agents = agents.parent / '.AGENTS.md.sdlc-install-tmp'
        text = original.decode() if original is not None else ''
        destinations = {name: safe(root, name) for name in files}
        if receipt.exists():
            previous = json.loads(receipt.read_text())
            if previous != manifest:
                raise ValueError('Different package version/content. Automatic upgrades are unsupported; preview a fresh install in a temporary directory and review a migration separately.')
            differences = [name for name, path in destinations.items()
                           if name != CONFIG and (not path.is_file() or sha(path.read_bytes()) != manifest['files'][name])]
            if differences or ROUTER not in text:
                raise ValueError('Installed scaffold was customized or is incomplete; preserve it and review a migration: ' + ', '.join(differences or ['AGENTS.md router']))
            if not destinations[CONFIG].is_file():
                raise ValueError('Verification configuration is missing; restore it through a reviewed change.')
            config = json.loads(destinations[CONFIG].read_text())
            print('Installed scaffold matches package; no files changed.')
            print('Verification: ' + ('configured; inspect checks before use.' if config.get('checks') else 'UNCONFIGURED; choose real project checks in ' + CONFIG))
            return
        conflicts = [name for name, path in destinations.items() if path.exists()]
        runs = safe(root, 'runs')
        if runs.exists() and (not runs.is_dir() or any(runs.iterdir())):
            conflicts.append('runs (existing work)')
        for top in ['stages', '_shared', '_system']:
            entry = safe(root, top)
            if entry.exists() and (not entry.is_dir() or any(entry.iterdir())):
                conflicts.append(f'{top} (existing content outside this package)')
        if tmp_agents.exists():
            conflicts.append(f'{tmp_agents.name} (stale installer temp file)')
        if conflicts or '<!-- AI-Native SDLC Router -->' in text:
            raise ValueError('Unmanaged or partial scaffold exists; no files changed. Review migration separately: ' + ', '.join(conflicts or ['AGENTS.md router']))
        print('Create: ' + ', '.join(sorted(files)))
        print('Append SDLC router to AGENTS.md; preserve existing instructions.')
        if check:
            print('Preview only; verification will remain UNCONFIGURED.')
            return
        fresh_dirs = {parent for target in (*destinations.values(), receipt) for parent in target.parents if parent != root and root in parent.parents and not parent.exists()}
        created = []
        agents_attempted = False
        router_written = False
        install_error = None
        try:
            for name, data in files.items():
                target = destinations[name]
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    created.append(target)
                    stream.write(data)
                if name.startswith('_system/scripts/'):
                    target.chmod(0o755)
            # Best-effort concurrent-edit check: an edit after this comparison can still be overwritten by replace() below.
            if (agents.read_bytes() if agents.exists() else None) != original:
                raise ValueError('AGENTS.md changed during initialization.')
            agents_attempted = True
            tmp_agents.write_bytes((text + ('\n\n' if text else '') + ROUTER + '\n').encode())
            if agents_mode is not None:
                tmp_agents.chmod(agents_mode & 0o777)
            tmp_agents.replace(agents)
            router_written = True
            with receipt.open('x') as stream:
                created.append(receipt)
                json.dump(manifest, stream, indent=2)
                stream.write('\n')
        except Exception as error:
            install_error = error
            cleanup_errors = []
            for target in reversed(created):
                try:
                    target.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    cleanup_errors.append(f'{target}: {cleanup_error}')
            if agents_attempted:
                try:
                    if router_written:
                        if original is None:
                            agents.unlink(missing_ok=True)
                        else:
                            agents.write_bytes(original)
                    tmp_agents.unlink(missing_ok=True)
                except OSError as cleanup_error:
                    cleanup_errors.append(f'{agents}: {cleanup_error}')
            for fresh in sorted(fresh_dirs, reverse=True):
                try:
                    fresh.rmdir()
                except OSError:
                    pass
            if cleanup_errors:
                raise RuntimeError('Rollback incomplete: ' + '; '.join(cleanup_errors) + f'; original error: {error}') from error
            raise
        print('Scaffold installed. Verification is UNCONFIGURED and will fail until real checks are selected. Read _system/SDLC.md.')
    finally:
        try:
            lock.rmdir()
        except FileNotFoundError:
            pass
        except OSError as lock_error:
            if install_error is None:
                raise RuntimeError(f'Installer finished but .sdlc-init-lock cleanup failed: {lock_error}; remove it manually.') from lock_error
            raise RuntimeError(f'Installation failed: {install_error}; .sdlc-init-lock cleanup also failed: {lock_error}; remove it manually.') from install_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target', help='Explicit target project checkout')
    parser.add_argument('--check', action='store_true', help='Preview installation or validate an existing install without changing scaffold files')
    args = parser.parse_args()
    try:
        install(Path(args.target), args.check)
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
