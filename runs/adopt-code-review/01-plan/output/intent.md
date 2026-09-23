# Intent: Adopt `code-review` Skill into tink-skills

## Problem Statement
The `tink-skills` repository currently contains scouting, cleaning, commitment, and interrogation skills, but lacks an automated, two-axis code review mechanism to evaluate diffs against documented coding standards and functional specs prior to PR generation.

## Objectives
1. Adopt the standalone `code-review` skill from the Tink library into `.agents/skills/code-review` and register it in `skills/code-review`.
2. Clean and harden `SKILL.md` to remove unportable external commands (`/setup-matt-pocock-skills`) while keeping the 12 Fowler smell heuristics intact.
3. Validate repository integrity and skill registration through `tink skill check`.
4. Ensure deterministic integration with the existing SDLC workflow.

## Acceptance Criteria
- `code-review` is added via `tink skill add` and passes `tink skill check`.
- `SKILL.md` contains refined frontmatter and instructions without broken tool references.
- Jev fit analysis confirms eligibility (`eligible_for_ranking: true`).
- Verification test suite (`python3 -m unittest discover -s tests`) passes cleanly.
