# Measurement review: grill-me-with-jev

Date: 2026-09-21. Source: [experiment plan](../plans/grill-me-with-jev-experiments.md).
The activation/ablation and long replay used version 1.2.0; its exact core is
[snapshotted](../../skills/grill-me-with-jev/evals/results/evaluated-skill-1.2.0.txt).
The subsequent question-economy fix is version 1.2.1 and received a targeted retest.
This follows the [hardening review](grill-me-with-jev-review.md); that earlier
report's fingerprints describe version 1.1.0, not this revision.

## Decision

Ship only the broader, bounded trigger description and minimum-sufficient-question
rule. Retain all existing decision/authority invariants. Do not promote the ledger
prototype into the runtime, and do not claim Jev or Noul adds value on current data.
The small pilot has a ceiling effect and does not justify removing either globally.

## Activation

Twenty description-only cases: eight positives and twelve near-neighbor negatives,
including normal architecture review, explanation, implementation, load testing,
quoted trigger language, CI, and explicit no-interview requests.

| Description | True positives | True negatives | False positives | False negatives |
| --- | ---: | ---: | ---: | ---: |
| Original | 8 | 12 | 0 | 0 |
| Revised | 8 | 12 | 0 | 0 |

The original was evaluated by a fresh subagent; the revision by the local Codex CLI.
Neither saw expected labels. This is one pass per description, using different host
surfaces, not a controlled same-model gain estimate or the desktop's actual skill
router. The change makes intended scope explicit; it showed no measurable gain here.

Evidence: [cases](../../skills/grill-me-with-jev/evals/activation.json),
[baseline](../../skills/grill-me-with-jev/evals/results/activation-baseline.json),
[revision](../../skills/grill-me-with-jev/evals/results/activation-candidate.json).

## Jev / Noul ablation

Three synthetic tasks (webhook delivery, migration, on-call alerts), each evaluated
with local-only routing, Choice-only, Noul-only, and both. Same operational skill,
fixed candidate coverage, synthetic user answers, and investigation facts. Host
receives oracle answers only after asking. Review runs as a separate snapshot after
interview choices are declared settled, not as a completed saved-plan workflow.
Real TypeSafe outputs were prefetched and replayed; the successful run returned
`jev-1.13.0` for all six packets. Expected labels were not sent to the host or Jev.

All twelve corrected episodes produced the same measured result:

- Two required decisions resolved in one user interruption.
- Two host rounds to settled choices/review readiness.
- Zero required-choice omissions, unnecessary questions, synthetic user corrections,
  premature required-choice acceptances, or repeated decision IDs.
- Correct classification of all three named review concerns: two material, one
  already handled. These were supplied candidates, not newly discovered omissions.

| Arm (three tasks) | Host input tokens | Host output tokens | Host seconds | Provider input/output tokens | Provider seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| Local | 156,804 | 859 | 65.182 | 0 / 0 | 0 |
| Choice | 158,078 | 814 | 65.112 | 2,758 / 479 | 1.172 |
| Noul | 161,310 | 841 | 63.990 | 1,327 / 62 | 0.945 |
| Both | 158,144 | 854 | 67.304 | 4,085 / 541 | 2.117 |

Each arm reported 103,680 cached host input tokens (already included in input).
Host time sums serial calls within each trial; trials ran with concurrency two.
Provider costs are listed separately because cached advice was reused across arms;
add them to the corresponding arm for an uncached one-pass estimate. Fixed order,
cache effects, concurrent load, and one repetition preclude a latency winner claim.
These are actual CLI/provider usage fields and wall time, not model estimates.

**Finding:** no measured Choice or Noul decision improvement on this corpus. The
extra protocol/calls had measurable cost. A harder randomized, repeated corpus is
needed to decide whether either call earns its place, especially for candidate
selection where local judgment is uncertain. No automatic provider removal follows
from a three-case ceiling result.

### Corrections and preserved evidence

The first pilot supplied references to synthetic files but no way to inspect them,
so migration/alert readiness stayed blocked. It is archived under
`evals/results/pilot-unresolved-facts/`, not counted as an interview failure.
The rerun supplies identical oracle facts when each host requests investigation.
The initial live pass also received HTTP 529 on three of six provider requests;
fallback is not evidence of equal successful-provider performance.

Review audit then found the prefetched Noul packets contained pre-interview context,
while host review used settled choices. Those receipts/reviews are preserved under
`evals/results/pilot-pre-settled-review/`. Final Noul packets and their six affected
host reviews were rerun with the same settled choices. The summary uses the final
reviews. No expected labels or oracle decisions were changed to improve scores.

Evidence: [fixtures](../../skills/grill-me-with-jev/evals/ablation.json),
[metrics](../../skills/grill-me-with-jev/evals/results/ablation-summary.json),
[provider requests/results](../../skills/grill-me-with-jev/evals/results/provider.json).

## Retention

The 16-turn sequential replay is recorded in
[retention results](../../skills/grill-me-with-jev/evals/results/retention.json).
It replays the full previous transcript and ledger on every request, with two
irrelevant-background turns, a conditional cost, a parent change, a repeated
answer, scoped delegation, and a final stop/implementation utterance. It does not
exercise forced context compaction or recovery from a persisted artifact.

All 16 turns completed. Manual inspection found preserved PostgreSQL-only/Redis-
and-Kafka prohibitions, at-most-once delivery, no ambiguous-timeout retries,
encryption, changed 30-day audit retention, the failed $100 condition and explicit
dashboard exclusion at $120, metric-only delegation, and deferred cosmetic work.
The repeated A answer did not increment revision 5. The material retention change
advanced revision 7 to 8 and cleared the prior confirmation. Final response:
“Stopped — incomplete. No further questions.” It neither saved nor implemented.

Six of seven literal final-field checks passed. The G cost lookup failed: the
agent had already allocated G to another concern before the user introduced that
label, so it preserved the cost under J with history. This is not a perfect ID-
retention pass. It exposes label-collision ambiguity in this fixture and the value
of checking semantic history rather than silently moving the expected answer.
The fixture and failed literal check are preserved unchanged. Record-only
confirmation at turn 14 acknowledged the displayed incomplete revision; the host
explicitly retained unresolved blockers and did not claim completion or permission.

The successful prefix was resumed after one host-process failure at turn 9; the
failed attempt remains in `retention-interrupted.json`. The saved 16 successful
turns consumed 401,600 input / 20,677 output tokens and 694.797 seconds, excluding
that failed attempt. Full-history replay makes those costs grow with transcript
length; they are not estimates for a native persistent session. There was no
forced compaction or comparison to a model using the ledger prototype.
[Literal assessment](../../skills/grill-me-with-jev/evals/results/retention-assessment.json).

## Question economy

Turn 12 of the retention replay asked whether to prohibit replay of an event after
an ambiguous timeout despite already accepted at-most-once delivery and no-retry
semantics. This is a plausible duplicate/entailed decision, although a separately
scoped manual replay feature could have changed the interpretation.

Version 1.2.1 replaces a generic duplicate-question instruction with an explicit
instruction to derive consequences forced by settled answers. A focused fresh CLI
case excluding any new manual-replay feature returned `ask: false` and recorded a
derived requirement. This is one targeted successful retest, not proof that all
redundant questions are eliminated. Its host used 17,296 input / 71 output tokens
and 5.997 seconds. [Evidence](../../skills/grill-me-with-jev/evals/results/question-economy.json).

## Deterministic bookkeeping experiment

[Prototype](../../skills/grill-me-with-jev/evals/ledger_experiment.py) and
[counterexample tests](../../tests/test_grill_ledger_experiment.py) are isolated
under evals. Ten direct software checks cover atomic cycle rejection, unresolved
and parked nodes, transitive reassessment, unaffected answers, no-op revisions,
actual answer versus recommendation, deferred parents, stale confirmation, and
snapshot isolation, inactive prerequisites, and rejection of mutable dependency edges.

The utility marks descendants dirty; it does not decide whether their answers are
invalid, interpret delegation, assess materiality, or evaluate conditional truth.
It is not imported or invoked by the runtime skill. Its tests show bookkeeping
properties only, not a behavioral improvement or a validated storage protocol.
There is no prompt-versus-ledger controlled retention comparison yet, so promotion
would be premature. Host integration and persistence would add costs not measured.

## Changes, verification, and repeatability

- Expanded trigger vocabulary and explicit near-neighbor exclusions.
- Added the two-reasonable-answers consequence test and decisions-per-interruption
  objective. Preserved actual-answer history, prohibitions, dependencies, explicit
  incomplete termination, revision confirmation, and no implied implementation.
- Added opt-in harness, fixed fixtures, raw receipts, and offline measurement checks.
- Full offline suite: 40 tests pass; skill metadata validation passes; includes structural, existing Jev-fit,
  experiment validation, and ledger prototype tests. No model calls in unit tests.

Commands and metric definitions are in the [evaluation guide](../../skills/grill-me-with-jev/evals/README.md).
Host executable was `codex-cli 0.154.0`, ephemeral/read-only with user config ignored.
No host model override was supplied; exact server model ID is not exposed in the
saved CLI events. Treat this as a runtime-specific pilot, not a pinned-model benchmark.
One delegated experiment agent failed on account usage before making changes; the
local CLI worked and all executed trials are recorded. No quota reset or account
setting change was made. No changes were made to `.agents/skills/`, and no commit,
push, provider installation, or global hook was performed.

The provider schema was read from the [official HTTP reference](https://docs.typesafe.ai/api.md)
and [TypeSafe skill](https://raw.githubusercontent.com/typesafe-ai/skills/main/skills/typesafe-ai/SKILL.md).
No source-code or credential payload was sent; only synthetic evaluation state.

## Outcome and remaining evidence gaps

The narrow source changes and measurement tooling are complete and locally verified.
This work does not establish general Jev value, actual-router accuracy, exact node-ID
retention, or a runtime-ledger advantage. The next justified experiment is a harder,
repeated, randomized corpus with stable preallocated node IDs and real end-to-end
interview metrics. The current findings are sufficient to avoid expanding the
operational state machine or promoting the bookkeeping prototype prematurely.
