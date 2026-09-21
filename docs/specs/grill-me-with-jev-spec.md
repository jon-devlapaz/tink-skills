# Spec: grill-me-with-jev hardening

Derived from [intent](../intent/grill-me-with-jev-intent.md).
Status: local implementation scope; human release review pending.

## Requirements and acceptance

| ID | Requirement | Observable acceptance |
| --- | --- | --- |
| R1 | Investigate facts before asking | Inspectable facts cannot be routed to the user by a Jev vote; inaccessible facts are recorded as unknown. |
| R2 | Account for the whole decision graph | Active and parked unresolved nodes prevent completion; cycles become a joint decision or a factual investigation. |
| R3 | Preserve conditional answers | Record the predicate and investigate it; never settle on an unknown or false predicate. |
| R4 | Reassess changes without flapping | Traverse transitive descendants, preserve valid answers, park invalid ones until ready, and reopen only for a recorded semantic change. |
| R5 | Separate acceptance, delegation, and deferral | Scoped delegation accepts a valid recommendation; skip defers only non-blockers and stop ends questions without claiming completion. |
| R6 | Preserve prohibitions and answers | Actual answers and rejected alternatives survive recommendations, re-evaluation, and artifact generation. |
| R7 | Make completion deterministic | All unresolved nodes block completion; known blockers cannot be cleared by a low or skipped Noul. |
| R8 | Bound Jev advice | Validate typed results; one transient retry at most; partial failures fall back per item; no fabricated badges. |
| R9 | Separate authorization phases | Confirm a displayed revision, save only its plan artifact, then require a subsequent explicit implementation instruction. Material revisions invalidate confirmation. |
| R10 | Protect artifacts and truthfulness | Preserve unrelated files; no auto-commit; report actual review provenance, never certified completeness. |

## Design

The contract is prompt-native. The agent maintains a ledger with stable IDs,
statuses, prerequisites, activation predicates, evidence, recommendations, actual
answers, authority, and revisions. The displayed frontier is derived from that
ledger; glyphs do not change authority. Retraction is an event, not another state.
A fact can resolve through evidence, but a consequential preference requires user
choice or scoped delegation. Defaults remain labeled assumptions.

Use one authoritative transition/reference document. The core skill owns workflow,
completion, authorization, and display. The reference owns detailed transitions,
Jev integration/failure handling, and query definitions. Evaluations live outside
the operational prompt to avoid teaching the skill to echo test answers.

Jev selects among supplied candidates; it does not synthesize unnamed blockers or
authorize work. Candidate-specific Noul > 0.80 returns to triage. Unchanged candidates
are not repeatedly submitted; contradictory model votes do not reopen settled
answers without new evidence. Local review always accounts for known blockers.

Authorization is revision-bound: interview -> review -> confirmed-and-saved ->
implementation handoff. Stopped/incomplete is a valid user-requested outcome, not
successful completion. The strict workflow requires implementation instructions
after the save, rather than treating a premature request as future permission.

## Verification and limits

Structural unit tests validate metadata, links, and evaluation-fixture integrity;
they do not prove agent behavior. Behavioral evaluation uses independent fresh
agents applying the skill to fixed inputs, with transcripts reviewed against R1-R10.
No live Jev call is needed for the deterministic failure cases. Record model/runtime
coverage and provider limitations rather than claim universal production readiness.

## Alternatives rejected

- New Python state engine: would test a second implementation that does not govern
  the prompt-native interview.
- Probability-only completion: cannot account for known unresolved decisions.
- Mandatory deployment/CI setup: not necessary to harden the local skill.

## Measurement follow-up

The [experiment plan](../plans/grill-me-with-jev-experiments.md) evaluates discovery
of the skill, provider value, and state retention. The operational implementation
remains prompt-native. A ledger under evals is an isolated prototype, not a second
implementation claimed to enforce this contract. Trigger changes must preserve
non-interview requests; question selection must require materially different
outcomes between reasonable answers. Existing R1-R10 remain binding.
