---
name: skill-eval-loop
description: >
  Paired diagnostic of one agent skill — same task with and without the skill.
  Use when measuring whether a skill improves local outcomes under Hermes, Claude
  Code, Codex, or Pi, headlessly or with Herdr observation; also when independently
  authoring a missing eval suite before that comparison.
---

# Skill Eval Loop

Run one **paired diagnostic**: hold prompts, fixtures, model, tools, harness,
and trial count constant; vary only explicit availability of the target skill.
Forced suites activate the skill before the task. Autonomous schema-3 suites
leave the task unchanged and score trace-visible skill selection.

## Preconditions

Require:

- a target directory containing `SKILL.md`;
- an existing `evals/evals.json`, a supplied `--evals-path`, or authority to
  launch a fresh subagent to author the suite;
- references that pass every declared grader;
- an exact model identifier before live trials;
- a working executable and authentication for the selected harness;
- a Herdr-managed pane with `HERDR_ENV=1` only for `--observer herdr`.

Audit, dry-run, and the default headless live run do not require Herdr.

Before live trials, calculate and state the exact harness-invocation count:

```text
target invocations = 2 × trials × cases
judge invocations  = Σ(g_i × (1 + c_i + 2 × trials))
total invocations  = target invocations + judge invocations
```

Here `g_i` is case *i*'s number of `model_rubric` graders and `c_i` is 1 only
when that case declares a `counter_reference`. The judge total therefore has
three visible components: reference judges `Σg_i`, counter-reference judges
`Σ(g_i × c_i)`, and condition judges `Σ(g_i × 2 × trials)`.

One harness invocation may make multiple provider model calls when tools are
used, so exact provider-call count and cost stay unknown unless the harness
reports them. Wait for explicit authorization of the invocation total and this
uncertainty before starting paid trials.

Set `SKILL_EVAL_DIR` to the absolute path of this installed skill directory:

```bash
SKILL_EVAL_DIR=/absolute/path/to/skill-eval-loop
```

## Ask one at a time

Ask exactly one open question per message and wait for the answer. Skip topics
the user already settled. Setup remediation may interrupt: ask only whether to
apply the stated fix, wait, then resume the topic list.

Order:

1. execution harness
2. evaluation goal
3. target model
4. judge model (only when model rubrics require one)
5. observation mode
6. authorization for the pilot invocation count and provider-call uncertainty
7. whether to scale after a valid pilot

## Workflow

### 1. Choose the execution harness

Name every supported harness before the first evaluation command:

- `hermes` — Hermes Agent
- `claude-code` — Claude Code
- `codex` — OpenAI Codex CLI
- `pi` — Pi coding agent

Ask which to use unless the request already selects one. Match the harness
running this skill only when the user chose it. Confirm that harness's
executable and authentication, and pass `--harness` on dry-run and live
commands.

Complete when: `--harness` is fixed and the executable/auth check has passed
or a remediation proposal is waiting.

### 2. Independently author a missing suite

If `evals/evals.json` is absent and no `--evals-path` was supplied, launch a
fresh-context subagent before the coordinator reads or runs any case. The
subagent writes only `<target-skill>/evals/**` and follows
[the independent authoring protocol](references/eval-authoring.md).

Give the subagent the target path and schema path only — no parent conversation,
proposed answers, expected failures, intended fixes, candidate outputs, or prior
benchmark results.

Once authoring begins, freeze the target skill implementation for this run. The
coordinator may receive only the subagent's factual handoff and audit summary.
If authoring or validation fails, delegate repair to a new fresh-context
subagent or stop. If fresh subagents are unavailable, report the blocker and
leave suite writing out of the main chat.

Complete when: the subagent reports schema version 3, at least three distinct
cases, honest provenance, passing static audit, and no live model calls — or
an existing suite is left unchanged and work continues.

### 3. Audit the suite without calling a model

```bash
python3 "$SKILL_EVAL_DIR/scripts/audit_suite.py" \
  --skill-path /absolute/path/to/skill
```

Complete when: the audit returns `"valid": true`. On failure, report errors and
stop with target trials unstarted; suite repair needs separate authority.

### 4. Discover and pin models without calling one

Ask whether the goal is a quick diagnostic, a release decision, or portability
across model tiers. Classify the task as `simple`, `standard`, `complex`, or
`portability` from the skill surface and the authoring handoff — leave case
prompts, graders, fixtures, and references sealed from the main context.

```bash
python3 "$SKILL_EVAL_DIR/scripts/recommend_models.py" \
  --skill-path /absolute/path/to/skill \
  --harness selected-harness \
  --task-profile standard
```

The recommender queries authenticated harness-native inventory for Pi, Codex,
and Hermes. Claude Code has no stable non-interactive inventory command, so
collect exact ids from its model picker and rerun with
`--models exact-id-1,exact-id-2`. Availability, price, and quota come only from
live discovery or the user — invent none.

Show the budget, balanced, and quality frontier; disclose tier fallbacks and
unknown cost. For a release claim, prefer the intended deployment model. For
portability, plan separate runs across tiers. Use no judge when the suite is
fully deterministic. When model rubrics are unavoidable, recommend the strongest
available judge and disclose same-model-as-target risk.

Confirm the exact target model before any run command. Confirm the judge model
in a separate turn only if model rubrics require one. Prefer a one-trial pilot;
inspect validity, traces, grading, and actual cost before proposing more trials.

If discovery or setup fails, follow
[the setup remediation protocol](references/setup-remediation.md): state the
failed check and exact proposed fix, wait for confirmation before mutating,
then rerun the read-only check.

Complete when: the user has pinned exact model ids and acknowledges the pilot
invocation count, tier heuristic, provider-call and cost uncertainty, and judge
limitations.

### 5. Choose observation, dry-run the plan, authorize

Name both observation options before constructing the dry run:

- `headless` (default) — full evidence without a Herdr workspace
- `herdr` — mirror live transcripts into a retained 2×2 workspace; requires a
  Herdr-managed pane with `HERDR_ENV=1`

Ask unless already selected. Pass `--observer herdr` on dry-run and live only
when Herdr is chosen, and verify its environment before live trials. Workspace
path layout lives in
[the workspace layout reference](references/workspace-layout.md).

```bash
python3 "$SKILL_EVAL_DIR/scripts/run_skill_eval.py" \
  --skill-path /absolute/path/to/skill \
  --harness selected-harness \
  --model exact-provider/model-id \
  --trials 1 \
  --dry-run
```

Default output resolves under:

```text
<agent-skills-root>/.eval-runs/<skill-name>/<run-id>/
```

`--output-dir` may override; the runner rejects paths inside the active
`skills/` directory.

Present the validated plan as a compact two-column Markdown table (not a
bullet list). Rows: harness, target model, judge model when present, trials per
case, cases, paired trials, observation, credential status, target invocations,
reference judges, counter-reference judges, condition judges, judge invocations,
and total harness invocations — **bold the total**. State above the table that
the dry run created no provider model calls, artifacts, workspaces, or panes;
it only derives the exact harness invocation plan. Live provider-call count and
cost remain unknown until the harness reports them.

Complete when: the plan names skill, harness, exact model, trial count, pair
count, exact harness-invocation count, counterbalanced order, observer, and an
output path outside `skills/`; dry-run created no files, workspaces, or panes;
and the user has authorized observation mode, pilot invocation count, and
provider-call uncertainty.

### 6. Run the paired pilot

```bash
python3 "$SKILL_EVAL_DIR/scripts/run_skill_eval.py" \
  --skill-path /absolute/path/to/skill \
  --harness selected-harness \
  --model exact-provider/model-id \
  --trials 1
```

Add `--judge-model exact-provider/model-id` only when the suite contains a
`model_rubric` grader. Judge calls use the same harness with skills disabled
and that harness's strictest supported tool posture (exact allowlist, disabled
toolset, or sandbox-only — recorded in the run artifact). Prefer deterministic
graders.

The runner owns counterbalance (odd trials control-first; even trials
treatment-first), reference validation, provenance hashes, and post-invocation
trace-attested model identity checks. A missing or mismatched judge identity
stops on the first reference judge; without model rubrics, a missing or
mismatched target identity stops after the first target invocation. Forced Codex
treatment also requires trace-visible access to the full structured skill
payload before downstream grading.

Raw harness traces are the evidence owner. Herdr, when enabled, focuses a
retained workspace once, reuses condition panes sequentially, and routes model-
rubric calls through the judge-results pane; the workspace stays open after
completion, failure, or cancellation, is renamed with terminal status, and sends
one notification.

On Ctrl-C, stop the active harness process, preserve partial artifacts, and
require `run_state.json` to report `"status": "cancelled"` and
`"valid": false`.

Complete when: the pilot pair finishes and `run_manifest.json` plus
`benchmark.json` exist. For an invalid run, preserve evidence, report the
cause, and start a new run only after correcting it. For a valid pilot, report
observed counts, routing evidence, actual cost, and limits, then ask whether to
scale to the user's confirmed trial count in a new run.

### 7. Interpret and (optionally) revalidate

Load [interpret-benchmark.md](references/interpret-benchmark.md) and report from
`benchmark.json` using its field definitions and claim boundaries.

To revalidate a copied or reviewed run:

```bash
python3 "$SKILL_EVAL_DIR/scripts/aggregate_benchmark.py" \
  --run-dir /absolute/path/to/run
```

Aggregation fails on missing artifacts, hash drift, inconsistent grading,
control exposure, or an installed payload that differs from the evaluated
skill. It reparses hashed runtime-attestation traces instead of trusting cached
routing booleans in the manifest.

Complete when: the interpretation matches the reference's claim boundaries, and
if revalidation ran, the regenerated benchmark has `"valid": true` (otherwise
the integrity failure is reported and the run preserved).

## Progressive disclosure

- Independent suite authoring:
  [references/eval-authoring.md](references/eval-authoring.md) and
  [references/eval-suite-schema.md](references/eval-suite-schema.md) — author
  subagent only, before trials.
- Setup remediation:
  [references/setup-remediation.md](references/setup-remediation.md) — after a
  failed environment or model-discovery check.
- Retained evidence layout:
  [references/workspace-layout.md](references/workspace-layout.md) — when
  inspecting run artifacts or Herdr workspaces.
- Result field map:
  [references/interpret-benchmark.md](references/interpret-benchmark.md) —
  after a finished or revalidated run.
