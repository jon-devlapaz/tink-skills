# Skill Cleanup Audit: `skills/code-review/SKILL.md`

## Overview
Worker 2 (Refactor Agent) performed an in-place editing pass on `skills/code-review/SKILL.md` following the `skill-cleaner` workflow and guidance.

## Changes & Rationale

1. **Frontmatter Cleanup**:
   - Preserved valid `name: code-review`.
   - Tightened `description` to be concise, accurate, and trigger-friendly while avoiding conversational bloat.

2. **Removal of Broken / External References**:
   - Removed external reference: `The issue tracker should have been provided to you. If docs/agents/issue-tracker.md is missing, tell the user to run /setup-matt-pocock-skills.`
   - Replaced with standard spec sourcing: checking commit messages directly for issue/PR numbers (`#123`, `Closes #45`, `!67`), accepting a user-supplied spec path/link, or checking repo spec directories (`docs/`, `specs/`, `.scratch/`).

3. **Style & Constraint Modernization**:
   - Removed unnecessary MUST/NEVER phrasing and filler phrases across instructions.
   - Restructured instructions into lean, imperative guidance with clear rationale.

4. **Domain Semantics & 12 Fowler Code Smells**:
   - Preserved the two independent evaluation axes: **Standards** and **Spec**, keeping their parallel execution and side-by-side reporting model.
   - Kept all 12 Fowler code smells intact with descriptions and concrete remedies:
     1. Mysterious Name
     2. Duplicated Code
     3. Feature Envy
     4. Data Clumps
     5. Primitive Obsession
     6. Repeated Switches
     7. Shotgun Surgery
     8. Divergent Change
     9. Speculative Generality
     10. Message Chains
     11. Middle Man
     12. Refused Bequest
   - Kept the "Why two axes" section intact to retain the design rationale that prevents one axis from masking the other.

## Line Count Statistics

- **Baseline line count**: 87 lines
- **Cleaned line count**: 84 lines
- **Net change**: -3 lines (~3.45% trimmed)
*(Note: As per `skill-cleaner` principles, line count reduction is incidental; substantive clarity and eliminating stale external dependencies while preserving all 12 smell definitions and two-axis mechanics were the primary objectives.)*

## Verification Checklist

- [x] Frontmatter valid (`name` and `description` present and intact).
- [x] Broken external references (`docs/agents/issue-tracker.md`, `/setup-matt-pocock-skills`) removed.
- [x] Spec source detection relies on commit messages, user-supplied path, or repo spec paths.
- [x] All 12 Fowler smells present with definitions and remedies.
- [x] Dual-axis review architecture (Standards and Spec) fully preserved.
