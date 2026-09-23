# Plan: feat-engine — Feature Extraction, Compatibility Evaluation, and Risk Profiling Engine

**Derived from:** `02-design/output/spec.md`  
**Status:** approved  
**Implementer:** Agent: Implementer (Pi Subagent in Worktree)  
**Date:** 2026-09-22  

## 1. Files That Change
- `feat_engine.py`: Core static analysis engine, vector normalizer, compatibility evaluator, risk profiler, and CLI entrypoint. Zero external dependencies (Python 3.9+ stdlib only).
- `skills/feat-engine/SKILL.md`: Skill definition, frontmatter triggers, operational guidelines, and CLI reference.
- `tests/test_feat_engine.py`: Comprehensive test suite testing all AST visitors, shell scanners, vector determinism, risk calculations, compatibility matrix, and E2E CLI execution.
- `runs/feat-engine/test-lock.json`: Verification test lock binding `tests/test_feat_engine.py`.

## 2. Order of Work
1. **Contract Test Authoring & Baseline Locking**:
   - Write comprehensive test suite `tests/test_feat_engine.py` covering all functional requirements in `spec.md`.
   - Lock tests into `runs/feat-engine/test-lock.json` using `python3 _system/scripts/sdlc.py lock-tests feat-engine tests/test_feat_engine.py`.
2. **Worktree Code Implementation (Agent: Implementer)**:
   - Dispatch Implementer subagent to `/Users/jondev/dev/active/tink-skills-feat-engine`.
   - Implement `feat_engine.py` with:
     - `parse_frontmatter`: Zero-dependency YAML frontmatter parser.
     - `PythonASTVisitor`: Traversing AST nodes for modules, calls, env lookups, writes.
     - `scan_shell_script`: Lexical scanner for shell commands and dangerous flags.
     - `FeatureExtractor`: Aggregating metadata, code analysis, and asset metrics.
     - `VectorNormalizer`: Continuous/discrete normalization and SHA-256 canonical hashing.
     - `CompatibilityEvaluator`: Multi-harness matrix validation (`pi`, `claude`, `codex`, `generic`).
     - `RiskProfiler`: 4-factor scoring with redline overrides.
     - CLI entrypoint (`main`) supporting `--json`, `--check-compat`, `--risk-threshold`, `--output`.
   - Implement `skills/feat-engine/SKILL.md` with Agent Skills frontmatter and operational rules.
   - Run local unit tests in the worktree: `python3 -m unittest tests/test_feat_engine.py`.
3. **Auditing & Refinement (Agent: Auditor)**:
   - Run `skill-cleaner` audit on `skills/feat-engine/SKILL.md` to ensure concise, contradiction-free, and trigger-accurate documentation.
   - Run `skill-scout` in VERIFY mode to confirm zero external dependency footprint and safe execution boundaries.
4. **Verification & Evidence Generation (Stage 04)**:
   - Sync implementation into candidate tree.
   - Run `_system/scripts/verify.sh feat-engine` in non-blocking background terminal (`bg_start`).
   - Confirm generated receipt at `runs/feat-engine/04-test/output/verification.json`.

## 3. Risks & Blast Radius
- **Zero Third-Party Dependencies**: No `requirements.txt` or pip packages modified; zero supply-chain exposure.
- **Isolation Guarantee**: All code authoring occurs in isolated worktree (`tink-skills-feat-engine`) preventing dirty state in base checkout.
- **Existing Suite Non-Regression**: 65 existing tests in `tests/` must remain passing.

## 4. Proof of Correctness
- Unit tests to run: `python3 -m unittest discover -s tests` (all existing tests + new `test_feat_engine.py`).
- Locked test baseline: `tests/test_feat_engine.py` locked via `sdlc.py lock-tests`.
- Verification command: `./_system/scripts/verify.sh feat-engine` yielding passing `verification.json`.
