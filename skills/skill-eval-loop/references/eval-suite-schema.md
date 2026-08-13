# Eval suite schema

Use this reference when authoring or repairing `evals/evals.json`.

Author missing suites only from a fresh-context subagent following
[the independent authoring protocol](eval-authoring.md). Do not pass it the
coordinator's conversation or candidate answers.

The runner accepts schema versions 2 and 3. Prefer version 3 because it binds
each case to retained provenance.

```json
{
  "schema_version": 3,
  "skill_name": "target-directory-name",
  "suite_type": "capability",
  "dataset_origin": "author_derived",
  "tool_profile": "no_tools",
  "activation_mode": "forced",
  "grader_discrimination": "case_contrast",
  "provenance_manifest": "provenance.json",
  "evals": []
}
```

Migration: remove the former `distribution_policy` object from version-3
suites. It was never applied to evaluator decisions, and current validation
rejects it rather than preserving significance-shaped dead configuration.

Use:

- `capability` for tasks with room for improvement;
- `regression` for behavior that should remain reliable;
- `author_derived`, `held_out`, or `production_regression` for dataset origin;
- `no_tools`, `read_only`, `read_write`, or `coding` for the shared harness
  tool profile. Enforcement varies by harness and is reported as a limitation.
- `forced` to expand the target skill before the task, or `autonomous` to
  expose only its metadata and measure whether the model reads `SKILL.md`.

Each case may declare a `counter_reference` beside `reference`:

```json
"reference": {"response": "a correct answer"},
"counter_reference": {"response": "a plausible but wrong answer"}
```

By itself, an optional counter is only an aggregate canary: it proves at least
one grader rejects the wrong answer. A schema-version-3 suite may make the
stronger claim with `"grader_discrimination": "case_contrast"`. Then every case
with a response-sensitive grader must provide a counter, the static audit proves
each deterministic response grader accepts the correct answer and rejects the
wrong one, and each `model_rubric` must do the same through the selected judge
harness before target trials. Aggregation checks the retained per-grader results
again; one permissive grader cannot hide behind another grader's rejection.

Omitting `grader_discrimination` is equivalent to `"none"` and preserves the
legacy aggregate canary. A counter-reference is part of the case, so adding or
changing one changes the case hash and the provenance manifest needs
re-registering.

Under `case_contrast`, the correct and wrong responses must be non-empty and
distinct. `counter_reference` is only valid when the case has at least one
response-sensitive grader (`response_contains`, `response_not_contains`,
`response_regex`, `markdown_table_column_regex`, or `model_rubric`). The
contrast grades the wrong response on the gold `reference` workspace, so
`file_exists` / `json_exact` alone cannot discriminate and are rejected at
load. Schema version 2 keeps its optional counter for compatibility and cannot
declare `case_contrast`.

Every condition receives the same task, fixture, model, harness, and tool
profile. The treatment additionally receives the selected harness's native
isolated skill installation. In `forced` mode the adapter explicitly activates
the skill. In `autonomous` mode the ordinary task is unchanged and
trace-visible access is scored against each case's routing class. The control
never receives the target skill.

## Case

```json
{
  "id": "stable-kebab-id",
  "behavior_class": "positive",
  "routing_class": "should_trigger",
  "prompt": "An ordinary request that does not name the skill.",
  "expected_skill_loading": "required",
  "fixture": "fixtures/stable-kebab-id",
  "graders": [
    {
      "name": "Creates the result",
      "type": "file_exists",
      "path": "result.json"
    }
  ],
  "reference": {
    "response": "",
    "workspace": "references/stable-kebab-id"
  }
}
```

`fixture` and `reference.workspace` are optional. Reference grading runs before
target trials and must pass every grader.

`expected_skill_loading` remains required by schema versions 2 and 3 for
compatibility. Do not interpret it as runtime evidence: the run manifest owns
the assigned `--skill` treatment, while `benchmark.json` separately reports
trace-visible injection and explicit access.

Allowed behavior classes are `positive`, `edge`, and `negative`.

Version 3 routing rules:

- `should_trigger` requires `expected_skill_loading: required`;
- `should_not_trigger` requires `expected_skill_loading: forbidden`;
- `ambiguous` requires either `required` or `forbidden`.

## Provenance

Version 3 requires one source record per case:

```json
{
  "schema_version": 1,
  "suite_sha256": "64-lowercase-hex-characters",
  "cases": [
    {
      "case_id": "stable-kebab-id",
      "origin": "production_regression",
      "source_id": "incident-2026-07-29-001",
      "source_type": "incident",
      "observed_at": "2026-07-29",
      "task_author": "reviewer-name-or-role",
      "artifact": "provenance/incident-001.json",
      "artifact_sha256": "64-lowercase-hex-characters",
      "case_sha256": "64-lowercase-hex-characters"
    }
  ]
}
```

Origin and source type must agree:

- `author_derived`: `author_scenario`;
- `held_out`: `independent_task`;
- `production_regression`: `production_trace`, `user_correction`, or
  `incident`.

## Graders

Every grader needs a unique, behavior-named `name`.

- `response_contains`: `value`
- `response_not_contains`: `value`
- `response_regex`: `pattern`
- `markdown_table_column_regex`: `column` and `pattern`
- `file_exists`: workspace-relative `path`
- `json_exact`: workspace-relative `path` and JSON `expected`
- `model_rubric`: version 2 uses `rubric`; version 3 uses grounded `criteria`

Prefer final-state graders such as `json_exact` and `file_exists`. A
`model_rubric` is evidence from a judge model, not ground truth.

## Best-practice coverage

Use at least three meaningfully different cases, not paraphrases. Include a
positive case and, where the skill has a real boundary, edge or negative cases.
Prompts should resemble ordinary user requests and must not name the skill,
quote its instructions, or expose its internal layout. Prefer deterministic,
behavior-focused graders and good/bad contrasts that every response grader
distinguishes when the suite will support a grader-discrimination claim. Record newly
invented cases honestly as `author_derived`; independence of the authoring
subagent does not make a case statistically held out.
