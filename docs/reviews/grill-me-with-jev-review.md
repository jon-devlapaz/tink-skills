# Review: grill-me-with-jev hardening

Status: local validation complete; release approval not claimed.
Chain: [intent](../intent/grill-me-with-jev-intent.md) ->
[spec](../specs/grill-me-with-jev-spec.md) ->
[build plan](../plans/grill-me-with-jev-plan.md) -> this review.
Contract: [SKILL.md](../../skills/interrogate/SKILL.md).
Cases: [evals.json](../../skills/grill-me-with-jev/evals/evals.json).

## Method and baseline

The original six Python tests passed before remediation. They asserted text
presence, not behavior. A separate read-only agent applied the original contract
to seven fixed cases before the edit. It reproduced missing cycle recovery,
conditional settlement ambiguity, incomplete transitive invalidation, missing skip
semantics, and conflicting completion attribution when Jev was unavailable.

Baseline excerpt: “Park both under Step 3. Neither can unlock. No cycle-breaking
rule exists.” On fallback: the completion badge required a confidence with no source.
It also identified that higher-priority user instructions can override a skill;
a prompt contract is not an enforcement boundary.

After changes, two fresh agents read only the revised core/reference and supplied
case inputs. The service evaluator also inspected the actual Python fixture. They
were not given expected answers, the prior audit, the spec, or the evaluation rubric.
They applied the scenarios read-only, reporting simulated user responses, ledger
transitions, and permitted side effects. The author compared these outcomes to
all 15 fixed case expectations. No live Jev calls, source implementation, or real
plan writes were exercised. These are independent behavioral simulations, not
an automated end-to-end proof or a production model benchmark.

## Case outcomes

| Case | Observed outcome | Assessment |
| --- | --- | --- |
| cycle | Joint decision or cycle-breaking fact; parked nodes cannot count as complete. | Pass |
| conditional | Investigate cost; $120 fails the <$100 condition and leaves the choice open. | Pass after targeted clarification |
| cascade | Reassess B/C transitively, preserve independent D; repeated A does not retract again. | Pass |
| soft-parent | Confident recommendation does not settle A or unlock B. | Pass |
| passive | Scoped delegation only; skipped blocker retained; stop ends questions as incomplete. | Pass |
| defer | Non-blocker retains reason/revisit condition; review can proceed. | Pass |
| prohibition | Postgres-only and Redis/Kafka exclusions persist across descendants/options. | Pass |
| triage-tie | Inspect repository fact; ties use local criteria; malformed result falls back. | Pass |
| provider-failure | Bounded retry, no auth/schema retries, per-item fallback, valid results retained. | Pass after notice-timing clarification |
| noul-known-blocker | Unresolved idempotency prevents gate entry; 0.80 cannot clear it. | Pass |
| noul-candidates | 0.81 routes named candidate to triage; 0.80 does not certify; no unchanged requery. | Pass after targeted clarification |
| premature-exit | Stop, report incomplete, no questions/confirmation/write/coding or queued permission. | Pass |
| artifact | Actual rejected/accepted choices preserved; unrelated file not overwritten. | Pass (simulated file-conflict branch) |
| revision | Parent change invalidates confirmation; earlier implementation request not carried forward. | Pass |
| webhook-three-turn | Actual fixture inspected, constraints retained, unresolved delivery/rate policy preserved. | Pass (three-turn simulation) |

## Feedback loop and corrections

1. State evaluator found ambiguity between provisional review candidates and known
   unresolved ledger nodes. Clarified that hypotheses remain provisional until
   assessed, while established blockers enter the ledger immediately. Targeted
   retest confirmed 0.81 -> factual triage -> justified disposition without false
   completion or repeated voting.
2. Distinguished an answer's condition from branch activation. A failed cost
   condition reopens the choice rather than hiding it. Targeted retest passed.
3. Explicitly limited earlier delegation: accepting an old recommendation does not
   authorize its replacement after invalidation without continuing delegation.
4. Provider evaluator found that a notice on an initial failed attempt could falsely
   claim local fallback after a successful retry. Notice now occurs on actual
   fallback after permitted retry; recovered attempts need no unavailable notice.
   Targeted retests confirmed successful recovery emits no unavailable notice,
   exhausted retries emit one fallback notice, and mid-session partial failures
   retain valid results.
5. Skill metadata validator rejected the original top-level `version`; moved it
   into `metadata.version`, after which validation passed.

## Three-turn response evidence

The evaluator observed PostgreSQL, three pods, and a single POST with a five-second
timeout in the fixture. It scoped absence claims to that function, rather than
claiming the whole service lacked infrastructure.

Turn 1 asked about duplicate delivery and shared rate-limit policy, with tradeoffs.
Turn 2: “Recorded: PostgreSQL directly; Redis and Kafka are prohibited.”
Turn 3: “Stopped — incomplete. Delivery idempotency and the rate-limit policy remain
unresolved. No final plan revision has been displayed, confirmed, or saved, so this
planning session has not reached implementation handoff.”

No Jev metric was invented, no Noul was used to override known blockers, and no
implementation or artifact write was performed by either evaluator.

## Deterministic verification

- `python3 -m unittest discover -s tests -v`: 24 tests pass (6 structural skill
  checks and 18 existing Jev-fit tests). Structural tests validate metadata,
  reference/artifact links, fixture integrity, and R1-R10 evaluation coverage.
- Skill creator `scripts/quick_validate.py skills/grill-me-with-jev`: `Skill is valid!`
- No claim that structural tests execute the interview or prove API behavior.

## Final independent review

A third read-only reviewer compared the final core/reference, spec, build plan,
and structural tests. It reported no actionable findings in graph transitions,
actual-answer persistence, provider handling, completion, or authorization. It
did not read this report, modify files, or use live APIs.

---

[MIT License](../../LICENSE).
