# Intent: feat-engine — Feature Extraction, Compatibility Evaluation, and Risk Profiling Engine for Agent Skills

**Originator:** Agent: Architect (SDLC full run)  
**Status:** draft  
**Date:** 2026-09-22  

## 1. Problem Statement
Current agent skill qualification, compatibility matching, and safety vetting across the Tink ecosystem and SDLC pipelines rely heavily on subjective prompt-based reasoning or manual inspection. Skill repositories contain heterogeneous artifacts: Markdown directives (`SKILL.md`), YAML/TOML frontmatter metadata, helper Python/Bash scripts, bundled assets, and reference documents. 

Without a standardized, deterministic static extraction engine:
1. **Compatibility is opaque**: Harnesses (such as `pi`, `claude`, `codex`, `gemini`) cannot automatically verify whether a skill requires unavailable CLI tools, unsupported runtime environments (e.g., Python 3.11 vs 3.9), or missing host features.
2. **Security & Risk vetting is ad-hoc**: Unvetted skills may silently execute destructive filesystem operations (`rm -rf`, raw disk writes), initiate unauthorized network egress (exfiltrating workspace data), access or leak sensitive environment variables and credentials, or request unbounded autonomous execution loops without human confirmation boundaries.
3. **Reproducibility is missing**: Different agents evaluate skill capabilities and risks inconsistently, leading to unrepeatable audit outcomes and unreliable policy gates.

## 2. Proposed Outcome
Develop `feat-engine` — a high-performance, deterministic static analysis engine and accompanying skill (`skills/feat-engine/SKILL.md`) that delivers:
1. **Multi-Modal Static Feature Extraction**: Recursively inspects a skill package directory without executing untrusted code, extracting structured metadata from Markdown frontmatter, natural language skill bodies, and Python/Bash helper scripts (via Python's `ast` parser and lexical tokenizers).
2. **Deterministic Vector Schema & Fingerprinting**: Generates a canonical, normalized feature representation with an invariant cryptographic fingerprint (`sha256:vector_hash`) guaranteed to produce identical results across operating systems and execution runs.
3. **Harness & Environment Compatibility Evaluation**: Evaluates candidate skills against target agent harness specifications, checking tool dependencies, shell binary prerequisites, and runtime constraints to produce a categorical compatibility verdict (`compatible`, `compatible_with_adaptation`, `incompatible`).
4. **Multi-Factor Risk Profiling**: Computes deterministic safety scores across four orthogonal risk dimensions:
   - Destructive filesystem operations (deletion, truncation, arbitrary overwrites);
   - External network egress (sockets, HTTP requests, exfiltration endpoints);
   - Credential and secret exposure (access to private keys, tokens, `.env` files);
   - Autonomy escalation level (background processes, self-modification, unprompted subagent loops).
   Maps scores against configurable policy thresholds (`allow`, `warn`, `block`).
5. **Dual Interface**: Exposes an importable Python module (`feat_engine`) and a zero-dependency CLI (`python3 -m feat_engine` or `feat_engine.py`) producing structured JSON for CI/SDLC pipelines.

## 3. Affected Users and Systems
- **Users / Roles**:
  - Agent Architects and Tech Leads: Verifying and gating candidate skills before adoption into projects.
  - Security Auditors: Auditing third-party and community skills for malicious or unsafe capabilities.
  - Automated SDLC Agents: `skill-scout`, `manage-tink`, and stage verification runners requiring fast, local, reproducible qualification metrics.
- **Services / Repos / Modules**:
  - `skills/feat-engine/`: Skill documentation, frontmatter, operational references, and entrypoint scripts.
  - Core engine module: `feat_engine.py` (stdlib-only, zero dependencies).
  - Verification & Testing: `tests/test_feat_engine.py` exercising 100% of feature extraction, risk scoring, and compatibility logic.
  - Integration downstream: Integrates with `skill-scout` qualification ladders and SDLC stage 02/04 gates.

## 4. Constraints & Boundaries
- **Zero Third-Party Dependencies (Non-Negotiable)**: Implemented exclusively using the Python standard library (compatible with Python 3.9+). No external dependencies (e.g., no `pydantic`, `pyyaml`, `requests`, `numpy`).
- **Strictly Static Analysis**: Untrusted candidate code must NEVER be imported, evaluated (`eval`/`exec`), or invoked. AST parsing and lexical extraction must be resilient to syntax errors and malicious constructs.
- **Cryptographic Determinism**: Vector serialization must be strictly canonicalized (`json.dumps(..., sort_keys=True, ensure_ascii=True, allow_nan=False)`) ensuring byte-identical hashes across runs.
- **Performance Budget**: Target execution latency ≤ 50ms for typical skill packages (≤ 2MB total size), with a hard ceiling of 500ms for large repositories.
- **Explicitly Out of Scope**:
  - Dynamic runtime sandboxing (e.g., eBPF, Docker containers, hypervisors).
  - Automated code remediation or automatic refactoring of detected vulnerabilities.
  - Remote registry hosting or network-based vulnerability database syncing.

## 5. Open Questions
- **D1 (Extraction Mechanism)**: Can static AST and regular expressions reliably detect obfuscated or indirect system calls, or is subprocess isolation required? (To be interrogated via Jev in Stage 02).
- **D2 (Vector Schema Stability)**: How should the vector schema handle versioning so that introducing new feature dimensions does not unnecessarily invalidate legacy compatibility caches?
- **D3 (Risk Scoring Model & Weighting)**: Should risk scores be linear weighted sums, max-severity thresholds, or vector category ceilings? How do we prevent false-positive blocking on legitimate admin/git skills?
- **D4 (Standard Library YAML Parsing)**: In the absence of `pyyaml`, what is the exact specification for robust, zero-dependency Markdown frontmatter YAML parsing?
