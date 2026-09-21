# Intent: grill-me-with-jev skill

Author: Jon & Agent. Status: Draft (Stage 1: Plan).

## Problem
When planning software architectures, agents either:
1. **Interrupt users too often** with trivial questions they could investigate themselves in code.
2. **Make unilateral assumptions** on consequential product forks without exposing tradeoffs.
3. **Quit too early** before uncovering silent failure modes or unasked prerequisites.

Existing solutions in the workspace each have half the answer:
- `jev-grill` has a powerful 3-way triage model (*Ask*, *Investigate*, *Continue*), but lacks formal state tracking and rigor.
- `jev-me` has a rigorous DAG frontier and an empty-frontier `Noul` stop check, but burdens Jev with heavy architectural synthesis instead of using it as an attention gatekeeper.

## Proposed Outcome
Create a third, unified skill named `grill-me-with-jev` in `skills/grill-me-with-jev/` that combines:
1. **Jev as an Attention Gatekeeper**: Automatically deciding whether a concern warrants user interruption, local code investigation, or continuation.
2. **Formal Frontier State Tracking**: Managing an explicit DAG of open (`❓`), confident (`❔`), parked, and settled (`➡️`) decision nodes.
3. **Empty-Frontier Integrity Gate**: Using Jev `Noul` to prevent premature session termination.
4. **Transparent Badge (`⚡️`)**: Emitting probability and confidence metrics for every Jev-informed step.
5. **Durable Plan Artifact**: Generating a committed `grill-plan.md` upon explicit user confirmation.

## Affected Users and Systems
- Developers and engineers planning features in Claude Code / Antigravity.
- `tink-skills` repository structure.
- TypeSafe Jev API (`typesafe-sdk` or HTTP client).

## Constraints
- Conforms to Agent Skills specification (`SKILL.md` with YAML frontmatter).
- Graceful degradation: if `TYPESAFE_API_KEY` is not set, degrade to host LLM reasoning without failing.
- Strict authorization: confirmation of the plan does not authorize code modification or tool execution; downstream changes require explicit separate approval.
- Follow the AI-Native SDLC Playbook (`intent.md` -> `spec.md` -> `plan.md` -> test -> review).

## Open Questions
1. Should `grill-me-with-jev` use an offline/online Python script (like `skill-scout/scripts/jev_fit.py`) or direct prompt/curl instructions as in `jev-me` and `jev-grill`?
2. Should the output artifact be named `grill-plan.md` or `grill-tree.md`?
