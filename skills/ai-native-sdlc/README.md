# AI-Native SDLC Skill

A portable, evidence-based software development lifecycle skill for AI coding agents.
This README describes the pre-packaging source workspace; after installation, the
operator manual is `_system/SDLC.md` in the target checkout.

## What is this?
`ai-native-sdlc` installs and operates an Interpretable Context Methodology (ICM) workflow inside any Git repository. It implements the 6-stage lifecycle from Anthropic's AI-Native SDLC Playbook with fail-closed cryptographic receipts, deterministic verification gates, and Tink toolchain integration.

## Installation via Tink

```sh
tink skill add jon-devlapaz/tink-skills --skill ai-native-sdlc
```

## Bootstrap a Project

In any repository checkout where you want to enable the SDLC workflow:

```sh
# 1. Preview changes (read-only)
python3 .agents/skills/ai-native-sdlc/scripts/init.py . --check

# 2. Install scaffold
python3 .agents/skills/ai-native-sdlc/scripts/init.py .
```

This sets up:
- `stages/`: 6 stage contracts (`01-plan` through `06-maintain`)
- `_shared/`: Templates (`brief.md`, `intent.md`, `spec.md`, `plan.md`, `REVIEW.md`)
- `_system/`: Portable engine `sdlc.py` and bash wrappers (`new-run.sh`, `status.sh`, `verify.sh`)
- `_system/SDLC.md`: Complete operator manual and recovery procedures

## Quick Workflow

```sh
# 1. Start a run (default: light profile with brief.md)
_system/scripts/new-run.sh fix-auth --kind bug

# 2. Check pipeline state
_system/scripts/status.sh fix-auth

# 3. Record human review decision
python3 _system/scripts/sdlc.py decide fix-auth 3 approved \
  --reviewer "Lead Engineer" \
  --source "PR #42" \
  --reason "Accepted scope and verification plan"

# 4. Lock bug reproduction test (for bug runs)
python3 _system/scripts/sdlc.py lock-tests fix-auth tests/test_auth.py \
  --source "Review ref" --failure-evidence "CI job #104"

# 5. Run deterministic verification
_system/scripts/verify.sh fix-auth
```

## Requirements
- Python 3.9+
- Git, Bash
- Optional: [Tink](https://github.com/jon-devlapaz/tink) & [tink-route](https://github.com/jon-devlapaz/tink-route)
