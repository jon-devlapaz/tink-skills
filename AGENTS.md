Canonical skill tree: `skills/`

Read published skills from `skills/`. That directory is the source for this repository, including `seed-me` and `skill-gate`.

Tink installs the locked set from `.tink/skills.toml` into `.agents/skills/`. `.agents/` is installed state, not source, and is gitignored. Every local `skills/<name>` skill, including `skill-gate`, belongs in that install and must match `skills/<name>`. `tink skill sync` copies a missing install from the published tree. Sync refuses to overwrite an install whose body already differs; remove that `.agents/skills/<name>/` directory and run `tink skill sync` again. Do not edit the installed copy.

## Anti-patterns (observed, load-bearing)

- **No silent skips.** A defined step is attempted or its skip reason is
  recorded in the transcript. Discretionary wording that lets a host skip
  without a trace is a defect in the instruction, not flexibility.


<!-- AI-Native SDLC Router -->
## SDLC Workspace
- Read `_system/SDLC.md` for setup, evidence boundaries, and recovery.
- Inspect `_system/scripts/status.sh` before creating a run.
- Read `stages/<stage-name>/CONTEXT.md` before processing a stage.
- Keep factory references in `_shared/` unchanged during feature runs.
- Use separate worktrees or clones for code-writing runs.
<!-- End AI-Native SDLC Router -->
