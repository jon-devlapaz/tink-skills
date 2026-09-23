# Change brief: Ecosystem Health Audit, Skill Refactoring & Lockfile Integrity

## Problem and outcome
The `tink-skills` repository maintains core agent capabilities (`ai-native-sdlc`, `grill-me-with-jev`, `skill-scout`) and runtime plugins. Over successive feature runs, several operational debts have accrued:
1. **Missing Lockfile**: `.tink/skills.toml` and `.tink/skills.lock` are absent, preventing reproducible verification across CI/agent environments.
2. **Ecosystem & Library Drift**: Stale discovery skills (`find-skills`) in the Tink library violate read-only safety by promoting unverified auto-installs (`npx skills add -g -y`). Furthermore, `skill-cleaner` contains outdated boundaries referencing `npx skills update` rather than Tink.
3. **Instruction Bloat & Heavy Scaffolding**: Core skills carry wordy passages, redundant MUST/NEVER stacks, and fragmented step navigation that increase context-window consumption.
4. **Untracked Test Assets**: Triage pilot evals and tests (`test_triage_pilot.py`) exist in working trees but lack unified maintenance integration.

**Outcome**: A clean, fully verified ecosystem where all skills pass `tink skill check` and `tink skill verify`, prompt bloat is trimmed with zero functional breakage, Jev risk frontiers are formally cleared, and SDLC stage maintenance receipts are recorded.

## Acceptance criteria
1. **Tink Integrity**: `tink skill check` confirms 9 operational skills; `.tink/skills.toml` and `.tink/skills.lock` generated and verified via `tink skill verify`.
2. **Jev Decision Gating**: All architectural decisions and candidate replacements stress-tested; decision ledger frontier cleared (Noul score <= 0.80).
3. **Targeted Refactoring**:
   - `skills/ai-native-sdlc/SKILL.md`: Streamline step flow, replace heavy MUST/NEVER phrasing with architectural rationale, preserve all verification invariants.
   - `skills/grill-me-with-jev/SKILL.md`: Tighten frontier display rules and ledger transitions; preserve single-question pacing and typesafe evaluation protocol.
   - `skills/skill-scout/SKILL.md`: Clarify read-only boundary and candidate qualification gates.
   - `skills/skill-cleaner`: Modernize package manager and boundary pointers to Tink.
4. **Verification**: Full test suite (`python3 -m unittest discover -s tests`) passes 100% green without regressions.
5. **SDLC Compliance**: Stage 3 decision recorded with formal reviewer, source, and rationale; `_system/scripts/verify.sh ecosystem-audit` passes and generates valid receipt.

## Approach and implementation checklist
- [x] Launch Swarm Worker A (Tink & Ecosystem Auditor) and Swarm Worker B (Scout & Comparator) for parallel inspection.
- [x] Run Jev architectural stress-test and `typesafe_evaluate` scoring on refactoring proposals and deprecations.
- [x] Initialize SDLC maintenance run `runs/ecosystem-audit` (`--profile light`).
- [ ] Dispatch Swarm Worker C (Code Surgeon / Cleaner) to perform isolated single-skill refactoring passes on target skills.
- [ ] Synchronize installed skills in `.agents/skills/` with cleaned `skills/` sources.
- [ ] Generate `.tink/skills.toml` and `.tink/skills.lock` using explicit `--source` mappings.
- [ ] Execute background verification suite (`bg_start`) across all unit tests and linters.
- [ ] Record human maintenance decision for Stage 3 in `runs/ecosystem-audit`.
- [ ] Run `_system/scripts/verify.sh ecosystem-audit` to generate verification receipt.
- [ ] Synthesize findings in dual-register ELI5 documentation (Junior Dev & VP of Eng).
- [ ] Package atomic commit and PR manifest via `ce-commit-push-pr`.

## Risks and verification
- **Regression in Contract Tests**: Scored at 0.13 (Grill) and 0.24 (SDLC) by Jev (negligible risk). Mitigation: run all 65 contract tests before and after each edit.
- **Unverified Mutation**: Empty-frontier boundary verified at 0.40 Noul score before any mutation is applied.
- **Lockfile Divergence**: Explicit local mappings (`--source`) guarantee deterministic digest computation matching filesystem trees.
