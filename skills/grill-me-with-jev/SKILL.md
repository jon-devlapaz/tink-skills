---
name: grill-me-with-jev
description: >
  Deprecated alias. Use the `interrogate` skill for decision-tree planning,
  grounded fact-finding, and pre-intent handoff. This shim exists so older
  install links and docs resolve without breaking.
---

# grill-me-with-jev (deprecated)

This skill name is retired. Use **`interrogate`** instead.

## What to do

1. Load and follow [`../interrogate/SKILL.md`](../interrogate/SKILL.md) (skill name: `interrogate`).
2. Do not expect Jev triage, TypeSafe protocol, or legacy grill-me eval machinery — those were removed in favor of interrogate's broader triggers and epistemic lenses.
3. For new installs, prefer:
   ```console
   tink skill add jon-devlapaz/tink-skills --skill interrogate
   ```

## Why this shim exists

Older README links, stage contracts, and `tink skill add ... grill-me-with-jev` invocations still appear in the wild. This redirect keeps discovery working while the canonical skill is `interrogate`.
