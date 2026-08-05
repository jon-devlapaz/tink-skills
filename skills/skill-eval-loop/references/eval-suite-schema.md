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
  "provenance_manifest": "provenance.json",
  "distribution_policy": {
    "minimum_pairs": 3,
    "minimum_effect_size": 0.1,
    "confidence_level": 0.95
  },
  "evals": []
}
```

`distribution_policy` remains required by the existing version-3 schema for
compatibility. The local evaluator records it without making a distribution or
significance decision.

Use:

- `capability` for tasks with room for improvement;
- `regression` for behavior that should remain reliable;
- `author_derived`, `held_out`, or `production_regression` for dataset origin;
- `no_tools`, `read_only`, `read_write`, or `coding` for the shared harness
  tool profile. Enforcement varies by harness and is reported as a limitation.
- `forced` to expand the target skill before the task, or `autonomous` to
  expose only its metadata and measure whether the model reads `SKILL.md`.

Each case may declare an optional `counter_reference` beside `reference`:

```json
"reference": {"response": "a correct answer"},
"counter_reference": {"response": "a plausible but wrong answer"}
```

`reference` proves the graders accept a correct answer. `counter_reference`
proves they reject a wrong one. Both are graded before any trial runs, and a
counter-reference that passes stops the run: graders that accept everything
report the same verdict for both conditions, so the paired comparison says
nothing. A counter-reference is part of the case, so adding one changes the case
hash and the provenance manifest needs re-registering.

`counter_reference` must include a string `response` (empty objects are
rejected). It is only valid when the case has at least one response-sensitive
grader (`response_contains`, `response_not_contains`, `response_regex`,
`markdown_table_column_regex`, or `model_rubric`). The canary grades the wrong
response on the gold `reference` workspace, so `file_exists` / `json_exact`
alone cannot discriminate and are rejected at load.

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
behavior-focused graders and references that pass those graders. Record newly
invented cases honestly as `author_derived`; independence of the authoring
subagent does not make a case statistically held out.
