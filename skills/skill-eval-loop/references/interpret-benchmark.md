# Interpret benchmark.json

Load this after a pilot or scaled run finishes, or when revalidating a copied
run. Report only local paired evidence.

## Fields

- `valid` and `artifact_valid` — evidence integrity, not causal attribution.
- `mechanism_valid` — whether the adapter assigned the sealed skill treatment,
  used the suite's activation mode, and kept the control unexposed.
- `runtime_attestation_complete` — whether the trace independently names skill
  injection or explicit skill access. Some harness traces omit this lower-layer
  event. Forced Codex treatment also requires explicit skill access while the
  run is being written; re-aggregation does not retroactively impose that
  write-time-only check.
- `outcome_verdict` — `improved`, `regressed`, or `no_difference`.
- `verdict` — top-level result; becomes `invalid` or `mechanism_unconfirmed`
  when those boundaries fail.
- `task_success.delta` — treatment rate minus control rate.
- `selection_verdict` and `routing.accuracy` — trace-visible access only, for
  autonomous schema-3 suites.
- `grader_discrimination` — `case_contrast` is validated only when every
  response-sensitive grader accepted the declared good response and rejected
  the bad one; `none` means optional counters were only aggregate canaries.
- `routing` — treatment availability, trace-visible injection, explicit access,
  selection errors, and control exposure.
- `operations.without_skill` and `operations.with_skill` — target-condition
  errors, timeouts, and usage. These established keys remain the target-only
  view.
- `operations.condition_judges` — rubric judges for both target conditions.
- `operations.references` — rubric judges used to validate correct references.
- `operations.counter_references` — rubric judges used to reject declared
  wrong-answer counter-references.
- `operations.full` — target conditions plus every included judge bucket.

Every operations bucket has `tokens`, `cost`, `tokens_coverage`, and
`cost_coverage`. Coverage reports `{reported, expected}` independently for
each metric. A numeric usage value means every expected record reported that
metric; `0` is possible only when no record was expected or all expected
records explicitly reported numeric zero. `null` means at least one included
expected record did not report usage. Older run snapshots without per-case
accounting metadata keep their target-condition usage, but their new judge and
full buckets intentionally show `expected: null` and `tokens`/`cost: null`;
do not infer zero usage from that missing historical metadata.

## Separation of claims

Treat assigned intervention, runtime attestation, routing decision, and task
outcome as separate evidence layers.

Always report those layers separately: artifact validity, mechanism validity,
runtime attestation, outcome, autonomous selection when measured, usage with
coverage, and the unproven list. `mechanism_unconfirmed` means attribution is
unproven; it does not mean the skill failed to improve the observed outcome.

Leave unproven: causal attribution, statistical significance, distribution
readiness, security approval, and blind-review independence. Condition order is
counterbalanced by the runner, but temporal drift remains possible. Tool
enforcement varies across harnesses — report the harness-specific posture from
the run artifact rather than assuming uniform control.
