# NASA-spike integration prompt (seed-me)

This folder holds 4 artifacts salvaged from the archived `agentic-se-skills`
repo (NASA Systems Engineering handbook lineage), pre-screened by Jev as
alpha for seed-me. Nothing here is wired into the interview. Your job: for
each artifact, decide PROMOTE (wire into SKILL.md steps), ADAPT (distill
then wire), or DROP (leave quarantined). Ask the operator when the decision
changes interview behavior, ledger shape, or session contracts.

## Context to load first

- `skills/seed-me/SKILL.md` — the 5 interview steps (triage, investigate,
  frontier, settle, pre-intent)
- `skills/seed-me/references/ledger-transitions.md` — ledger setup, ranking,
  dependency rules
- `skills/seed-me/references/epistemic-lenses.md` — opt-in lenses
- `skills/seed-me/scripts/session.py`, `viewer.py` — session lifecycle

## Artifact questions

### 1. requirements-taxonomy.md
- Step 1 shapes a working draft from goal/constraints/exclusions. Which of
  the 9 taxonomy categories earn labels in the draft (objective? assumption?
  acceptance criterion?) and which stay out?
- The never-promote-goals rule: does it become draft-shaping guidance, a
  grill question generator, or ledger node typing?
- Citations dangle at missing source-grounding pages. Strip or rewrite?

### 2. decision-analysis.md
- The frontier already ranks by consequence then risk with cited evidence.
  What does the criteria-matrix add — and where does it live: ledger node
  fields, a frontier-turn format, or the pre-intent record?
- The revisit-trigger convention: new ledger field or prose habit?
- Guardrail check: the playbook warns against retroactive requirements. Does
  seed-me's "confirmed lines become ledger nodes" already satisfy this, or is
  there a hole?

### 3. conops.md
- Intake currently extracts goal/constraints/exclusions. Do nominal vs
  off-nominal scenarios become a standard intake move, an opt-in lens, or a
  product-seed-only path?
- Candidate-requirements output: how do they enter the ledger — PROVISIONAL
  lines, a new node kind, or out of scope?
- Validation hooks: meaningful pre-intent, or post-handoff material? If the
  latter, say so and scope it out.

### 4. run_eval_contracts.py
- This checker enforces REQUIRED_FIELDS on `evals/*.md` naming one skill
  under test. Where do seed-me evals live, and who writes the first one?
- PROMOTE means moving this file to `skills/seed-me/scripts/` and wiring
  `tests/test_seed_me_eval_contracts.py` (already passing against the
  nasa-spike path). Until evals exist, the checker is convention-only — say
  so explicitly.
- Does the viewer or session contract need an eval hook, or does this stay a
  repo-hygiene check?

## Decision rules

- Prefer ADAPT over PROMOTE: smallest SKILL.md delta that changes interview
  behavior. Do not paste playbooks whole.
- Keep receipts (📜), single-decision pacing, and the ungrounded-question
  budget untouched unless the operator explicitly approves the change.
- Prove with pytest (`tests/test_seed_me_*.py`). Report what ran.
- Never commit. Leave changes unstaged for operator review.
