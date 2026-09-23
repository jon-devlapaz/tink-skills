## Cleaned: skills/feat-engine/SKILL.md

**Reads better because:** Introduces an actionable 3-step audit workflow directly below the invariant, resolves exit code and threshold boundaries, reorganizes the Python API from public entrypoint to low-level parsers, and eliminates duplication between top-level invariants and bottom safety boundaries.  
**Size:** 142 lines (645 words) → 161 lines (728 words) (+19 lines, net expansion to provide operational execution workflow)

### Conflicts resolved
- Exit code 3 vs default execution — Resolved ambiguity where exit code 3 was described unconditionally as "incompatible with target harness", whereas `feat_engine.py` only gates exit code on compatibility when `--check-compat` is explicitly passed. Clarified condition in exit code table.
- WARN score boundary — Reconciled `WARN: 0.30 - 0.70` with `BLOCK: >= 0.70` by making the interval mathematically exact: `0.30 <= score < 0.70`.
- Redline score forcing — Reconciled "ensures overall_score >= 0.70" with engine implementation forcing `overall_score = max(weighted_score, 0.70)`.

### What got tightened
- CLI command invocation — Replaced inconsistent `/path/to/skill` references with uniform `<skill_dir>` positional parameter.
- Option specification — Clarified `--check-compat` behavior when supplied with vs without optional harness argument (`default: pi when flag is given without argument`).
- Safety section — Retitled `Safety Boundaries` to `Security & Reliability Guarantees` and tightened points to avoid restating the top invariant verbatim.

### What got restructured
- Hoisted operational `Audit Workflow` — Placed a concrete 3-step execution guide (Run Static Audit → Evaluate Risk Verdict → Verify Harness Compatibility) immediately after the invariant so executing agents have clear operational flow before delving into architecture details.
- Inverted Python API documentation — Placed high-level facade methods (`analyze_skill`, `extract_features`, `profile_risk`, `evaluate_compatibility`) first, moving internal AST and lexical helper parsers (`parse_frontmatter`, `analyze_python_code`, `scan_shell_script`) to the bottom.

### Left alone on purpose
- Frontmatter `description` — Kept intact without shortening to preserve trigger matching accuracy across agent harnesses.
- Architecture ASCII diagram — Retained full 30-line pipeline diagram because it visually maps extraction nodes to risk profiling and compatibility evaluation stages.
- Risk factor table & weights (`0.35`, `0.25`, `0.25`, `0.15`) — Preserved full table and scope definitions because exact weighting and pattern scopes are critical for auditing transparency.

### Notes
- Executed without `.agents/skills/skill-creator/` present in repository; evaluated against house style derived from `AGENTS.md` and existing skill conventions.
