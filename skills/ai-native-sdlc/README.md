# AI-Native SDLC

Install an ICM-inspired local workflow into an explicitly selected Git checkout.
Editable Markdown holds intent and plans; JSON receipts track local decisions and
verification evidence. CI, authenticated approval, deployment, and monitoring remain
project integrations. Content hashes detect changes; they are not signatures.

## Install and configure

From this skill collection:

```sh
tink skill add jon-devlapaz/tink-skills --skill ai-native-sdlc
python3 .agents/skills/ai-native-sdlc/scripts/init.py . --check
python3 .agents/skills/ai-native-sdlc/scripts/init.py .
```

The initializer installs stage contracts, templates, runtime scripts, and the operator
guide at `_system/SDLC.md`. It preserves existing project instructions and refuses
conflicting or different-version scaffolds. Review a separate migration for upgrades.
Use a separate worktree or clone for code-writing runs.

**Verification starts unconfigured.** Set `_system/verification.json` to real project
checks before running verification. Tink integrity checking is optional and explicit.
Git needs an initial commit before verification. The runtime requires Python 3.9+,
Git, and Bash on a POSIX system; native Windows operation is not supported.

## Operate a run

```sh
_system/scripts/new-run.sh feature-name
_system/scripts/status.sh feature-name
```

Edit the generated brief and obtain actual human acceptance before recording the
review decision. Follow the installed guide for the complete decision command,
reproduction baseline for bug fixes, rejection/rework, and verification. Do not
paste fictional reviewer names or evidence into real runs. The full profile separates
intent, spec, and implementation plan; the light profile uses one reviewed brief.

Local status accepts unchanged candidate content after an evidence-only commit.
A release still needs CI for the actual merge revision and independent forge approval.

## Maintain this package

`assets/` is the canonical distributable scaffold in this repository. Do not update
it from an external sandbox generator. After an intentional payload change, choose
a release version and refresh the content manifest:

```sh
python3 skills/ai-native-sdlc/scripts/package.py --version 1.0.1
python3 skills/ai-native-sdlc/scripts/package.py --check
python3 -m unittest discover -s tests -p 'test_sdlc_*.py' -v
```

The manifest records payload content hashes, not publisher authenticity. Tests use
isolated temporary repositories and synthetic review fixtures, never real approvals.
The package intentionally has one runtime implementation; tests execute that payload.
