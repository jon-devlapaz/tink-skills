Canonical skill tree: `skills/`

Read published skills from `skills/`. That directory is the source for this repository, including `skill-gate`. `seed-me` is the external skill at https://github.com/jon-devlapaz/seed-me.

Tink installs the locked set from `.tink/skills.toml` into `.agents/skills/`. `.agents/` is installed state, not source, and is gitignored. Every local `skills/<name>` skill, including `skill-gate`, belongs in that install and must match `skills/<name>`. `tink skill sync` copies a missing install from the published tree. Sync refuses to overwrite an install whose body already differs; remove that `.agents/skills/<name>/` directory and run `tink skill sync` again. Do not edit the installed copy.

## Coding standards

- Read [`CODING_STANDARDS.md`](CODING_STANDARDS.md) before writing or reviewing a skill or its tests.

## Anti-patterns (observed, load-bearing)

- **No silent skips.** A defined step is attempted or its skip reason is
  recorded in the transcript. Discretionary wording that lets a host skip
  without a trace is a defect in the instruction, not flexibility.

## git-golden

A repository is `git-golden` when all of the following are true:

- It is checked out on `main` with a clean working tree.
- Local `main` is even with `origin/main`.
- Open issues and pull requests are tracked separately; they do not make the checkout unclean.
- The latest `Validate repository` run on `main` succeeded.

<!-- AI-Native SDLC Router -->
## SDLC Workspace
- Read `_system/SDLC.md` for setup, evidence boundaries, and recovery.
- Inspect `python3 _system/scripts/sdlc.py status` before creating a run.
- Read `stages/<stage-name>/CONTEXT.md` before processing a stage.
- Keep factory references in `_shared/` unchanged during feature runs.
- Use separate worktrees or clones for code-writing runs.
- Stage skills: see the Skills section of the current stage's CONTEXT.md.
- Need a specialised skill mid-task? `tink-route --receipt runs/<slug>/skills.jsonl "<what you need>"` prints it on stdout; exit 1 means none fits, so continue without one.
<!-- End AI-Native SDLC Router -->
