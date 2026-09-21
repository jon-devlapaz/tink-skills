# Measurement experiments

These files are evaluation infrastructure. The operational skill does not load
or invoke them. Measured results and limitations are recorded in
`docs/reviews/grill-me-with-jev-experiments.md` at repository root.

## Run

Offline checks (no model calls):

```sh
python3 -m unittest discover -s tests -v
```

Opt-in live experiments, from repository root:

```sh
python3 skills/grill-me-with-jev/evals/run_experiments.py activation
python3 skills/grill-me-with-jev/evals/run_experiments.py ablation
python3 skills/grill-me-with-jev/evals/run_experiments.py retention
python3 skills/grill-me-with-jev/evals/run_experiments.py retention --resume
python3 skills/grill-me-with-jev/evals/run_experiments.py score-retention
python3 skills/grill-me-with-jev/evals/run_experiments.py question-economy
```

These consume the current Codex CLI account's usage. Ablation additionally sends
synthetic fixture state to TypeSafe using `TYPESAFE_API_KEY` from the environment.
No secrets or real repository payloads are sent. Codex runs ephemeral, read-only,
with user config ignored; no host model override is supplied. Host tool calls
invalidate the trial. Only actual usage events and monotonic wall time count as
measurements. The harness does not install dependencies or modify account settings.
Archive `results/` before rerunning: output filenames are stable and overwritten.

## What each experiment establishes

- `activation.json`: description-only selection, 8 positives and 12 near-neighbor
  negatives. This is not the desktop skill router with all competing skills.
- `ablation.json`: three synthetic tasks, four arms (local, Choice, Noul, both).
  Fixed candidates and synthetic answers isolate routing and candidate assessment.
  Oracle facts are delivered on requested investigation. Expected labels and oracle
  answers are hidden from the host until requested. Review is a separate snapshot
  with all interview choices settled, not proof of an end-to-end completed plan.
- `retention.json`: 16 sequential user turns; each fresh request replays the full
  prior transcript and ledger. Measures answer/constraint retention and changes,
  not automatic compaction, checkpoint recovery, or a multi-hour real conversation.
- `question-economy.json`: focused regression for a consequence already forced by
  accepted choices. No expected label is passed to the model.
- `ledger_experiment.py`: deterministic storage, DAG readiness/cycle detection,
  transitive reassessment marking, and revision bookkeeping. Tests are direct
  software checks. They do not prove the model will supply correct semantic updates.

## Metrics and interpretation

Count required answered choices retained in the final host response, missing
required choices, unnecessary questions, user interruptions, repeated decision IDs,
acceptance before an oracle answer, and review classification. Report actual host
input/output/cached token counts and elapsed wall time. Provider receipts retain
request hashes, model version, token usage, elapsed time, failures, and retry attempts.
Provider packets are prefetched once and replayed across arms so advice is identical;
its separate cost must be added for the relevant arms. Do not count failure fallback
as evidence that successful Jev advice has no effect.

`turns_to_settled_choices` counts host rounds to review readiness, excluding final
confirmation/save. `synthetic_user_corrections` counts oracle replies redirecting
unnecessary questions; it is not an estimate of real-user satisfaction. The fixed
candidate set cannot measure discovery of risks never proposed by the host. Zero
errors on three tasks is a ceiling effect, not proof of equal general performance.
The pilot uses one repetition and a fixed arm order; latency differences are
confounded by caching, provider load, and concurrent execution. Use randomized,
repeated, harder real tasks before making a keep/remove or runtime migration decision.
