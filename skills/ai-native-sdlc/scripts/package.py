#!/usr/bin/env python3
"""Maintain/check the manifest for the canonical scaffold under assets/."""
import argparse
import hashlib
import json
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'assets'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check without writing')
    parser.add_argument('--version', help='Explicit release version for a manifest update')
    args = parser.parse_args()
    manifest_path = ASSETS / 'manifest.json'
    old = json.loads(manifest_path.read_text())
    files = {}
    for path in sorted(ASSETS.rglob('*')):
        if path.is_symlink():
            parser.exit(1, f'Symlink in package: {path}\n')
        if not path.is_file() or path == manifest_path or '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        files[str(path.relative_to(ASSETS))] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {'version': args.version or old['version'], 'files': files}
    if args.check:
        if manifest != old:
            parser.exit(1, 'Manifest does not match package contents. Update it for the release.\n')
        print('Package manifest matches all assets.')
    else:
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
