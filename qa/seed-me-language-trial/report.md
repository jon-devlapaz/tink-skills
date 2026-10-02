# Seed Me language trial — 2026-10-02

## Scope and decision

Base: `7a045e4` (`origin/main` when the branch was created). Work is isolated on
`codex/seed-me-controlled-language`. This trial changes Seed Me wording, its
question template, and the existing conduct checks for those labels. The required
Seed Me entry in `.tink/skills.lock` is refreshed to match the published tree. It does not
change ledger/session schemas, lifecycle scripts, UI, or installed skills.

## Sources inspected

- [Official ASD-STE100 overview](https://www.asd-ste100.org/about.html): consistent
  words and meanings. The overview and FAQ were available through web search;
  direct homepage/FAQ opens returned HTTP 403.
- [Official FAQ](https://asd-ste100.org/STE_faq.html): STE is for technical
  documentation. Short sentences and active voice can inform other writing.
  This is inspiration, not a claim of compliance or a controlled dictionary.
- [Digital.gov: Short and simple](https://digital.gov/guides/plain-language/principles/short-simple):
  common words, active voice, removing repetition, and consistent terms.
- [Anthropic: Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents):
  clear saved state and actual verification help later agents continue work.
  Our application: simpler wording must preserve evidence, unfinished work,
  and authority. The article does not validate this Seed Me change.

The NASA spike prompt and existing evaluation tests were inspected as prior
material. They are not evidence for this trial. Its old no-commit instruction
belongs to that integration experiment; the current request explicitly requires
commit and push. No dedicated dogfooding swarm was launched.

## Changes and retained purpose

| Change | Evidence and retained purpose |
| --- | --- |
| One short writing section shared by Lean and Full | Applies to every requested output type without a separate style manual. Keeps exact source quotes, commands, uncertainty, and required actions. |
| Remove repeated “If you pick B/A instead” sentences | Baseline technical/recommendation samples repeat the opposite option. Each revised row still states its comparative benefit, cost, and undo cost. |
| “Gate” becomes “To decide” in chat | Names the answer needed while keeping the owner and consequence. The internal `gate` field is unchanged. |
| Split recommendation caveats across lines | “Checked,” “Inference,” and “Assumptions” no longer combine conclusions and assumptions. Confidence, unchecked facts, change conditions, and invented numbers remain explicit. |
| Clarify instinct-first exception | Baseline found conflicting “only” wording. The question retains evidence, owner, answer needed, and ledger link; options and suggestion still wait. |
| “What we have not read” replaces “true but nobody has read” | Unread material stays in both contract formats and the close checklist without being labeled verified. |
| Replace the local-completeness status phrase | Says what the draft review checked and makes clear it did not verify implementation. All review steps remain required. |
| Update existing conduct checks and fixtures | New labels replace old ones without compatibility shims. A missing caveat is still rejected; each field is tested. These checks do not measure writing quality. |

No operational procedure was deleted. Detailed lifecycle and authority rules stay
in their existing locations. No broader refactor was justified.

## Evidence boundaries

The six paired examples use identical scenario inputs and the same synthetic
fixture. They are output samples, not completed interviews. Placeholder viewer
links in those samples are explicitly supplied context, not running services.
A separate dogfood run exercises real session commands with simulated operators.
Neither method provides human usability evidence. There is no LLM style score.

## First comparison and correction

The independent reviewer saw only unlabeled pairs and their fixture. Mapping is
saved separately. They preferred the revision for the rough draft, technical
question, recommendation, and hard choice; found no clear difference for the
assumption; and preferred the baseline stop message. These are reviewer judgments,
not human-readability measurements.

The first revised stop sample assigned a future decision to the “note owner”
without that role being established in its isolated context. We rejected that
sample as evidence of success. The writing instruction now requires the agent to
say when ownership is unassigned. Both sample versions also used a stopped-status
heading before explaining that no lifecycle command ran; the final sample must
make this distinction clear. The preliminary dogfood and first comparison are
retained; final examples and dogfood are rerun after the correction.

## Checks during development

- `python3 -m pytest tests/test_seed_me_*.py -q` could not start: system Python
  had no pytest. No test result was claimed from this attempt.
- `python3 -m unittest discover -s tests -p 'test_seed_me_*.py' -q`:
  95 tests passed with the browser class skipped because Playwright was absent.
- `uv run --with pytest python -m pytest tests/test_seed_me_*.py tests/test_qa_conduct.py -q`:
  109 passed, 41 browser tests skipped, 255 subtests passed.
- After adding the repository's pinned Playwright dependency through `uv`, the
  same targeted tests passed: 150 passed, 263 subtests passed, no skips.
- The first full unittest run failed two activation checks because the skill
  digest was stale. Updating only Seed Me's lock entry fixed both. The subsequent
  targeted run including `tests/test_activation_layout.py` passed 155 tests and
  272 subtests; full unittest passed 213 tests.
- The system-Python skill validator could not start because PyYAML was missing.
  `uv run --with pyyaml python /Users/jondev/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/seed-me`
  passed. Dependencies were supplied by `uv`; repository dependency files were
  not changed.

Final verification below supersedes these intermediate checks.

## Final tests

Run from the isolated worktree after the final skill edit and lock refresh:

```sh
uv run --with pytest --with-requirements tests/requirements-browser.txt python -m pytest tests -q
```

Result: **213 passed, 286 subtests passed, no skips** (57.50 seconds). This includes
all `tests/test_seed_me_*.py`, conduct tests, activation checks, and browser tests.

```sh
uv run --with pyyaml python /Users/jondev/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/seed-me
python3 -m compileall -q skills _system tests
bash -n _system/scripts/*.sh
git diff --check
```

All exited 0; skill validator reported `Skill is valid!`. Local reference links are
covered by `test_operational_references_resolve_inside_skill`. No style-score tests
were added. Final Seed Me tree digest:
`964135b64a09db267c5e1622acf1164bc9504b887b2bd79fdc4011ae24b97f93`.

The final six examples are in [final-examples.md](final-examples.md). Five were
rechecked without changes; the stop sample was regenerated. This is a targeted
correction after review, not a fresh blinded replication.

## Final wording review

[The independent follow-up](final-review.md) found no remaining critical meaning
loss or unsupported authority. The reviewer accepted the narrow editorial change
with explicit limits: fixtures are synthetic, reversal costs are supplied context,
and an output sample cannot prove lifecycle behavior. This follow-up was no longer
blind and was not treated as a second independent experiment.

| Case | Before → final observation |
| --- | --- |
| Rough idea | Repeated provisional labels → one clearly provisional draft; no solution accepted. |
| Technical question | Unexplained SQL and repeated contrasts → term explained outside exact quote, current behavior separated from proposed change. |
| Assumption | Unconfirmed default remains unconfirmed; no clear readability gain claimed. |
| Recommendation | Repeated contrasts and dense caveats → comparative rows and separate checked facts, inference, and assumptions. |
| Hard-to-undo choice | Instinct still comes first; required owner and ledger details are now explicitly retained by the instruction. |
| Stop | Initial revision failed the ownership check; corrected sample says owners are unassigned and operations are pending. |

Decision: retain the narrow change. Do not claim that every output became shorter
or that simulated operators establish human usability. The benefit shown here is
clearer labels and fewer repeated consequences, with the visible controls preserved.

## Dogfood attempts retained

The first setup initialized a session before goal confirmation and loaded the
Full reference while preparing Lean. It was stopped and excluded from success
claims. A subsequent small interview bundled three probes in one turn; its
contract also failed the existing strict conduct checker (missing required
knowledge-map parts and exact probe fields). These were interviewer mistakes;
no test or operational rule was relaxed to accept them. The final small interview
was restarted with one probe per turn.

A root-agent check also ran against that replacement interview's still-in-progress
draft. It exited 1 because acceptance checks and the knowledge map were not yet
written. This premature check is not a result for the finished contract. The final
checks below run only after the interviewer reports completion.

The root's strict ledger check found one more record-format failure in the completed
small interview: five `authority_source` fields contained the exact simulated
answers after a colon but lacked the quotation marks required by the existing
checker. The words and simulated authority were present; this was not treated as
a passing check. The ended record was preserved. A separate, explicitly labeled
replay rebuilds the record from those retained answers with quoted sources and
validates the lifecycle again. That replay is record repair and validation, not a
new independent interview or fresh usability evidence.


## Final dogfood result

[Dogfood report](dogfood/report.md), [small transcript](dogfood/small/transcript.md),
[hard-stop transcript](dogfood/hard/transcript.md), and the saved simulated
contracts preserve the operator-facing evidence. All operator answers are
simulated; no human confirmed a contract or authorized implementation.

The small interview kept each probe separate and preserved the operator's exact
scope. Its contract passes all four existing conduct checks. The repaired ledger
replay passes validity, source-quotation, and acceptance checks. The hard-stop
ledger passes applicable checks and retains its unresolved deletion blocker.
Both final viewers and the replay viewer were verified stopped with current
snapshots. The replay preserves the same semantic nodes, changing source quotation
formatting and recording transcript provenance.

Root verification commands (each finished with exit 0 and a nonzero item count):

```sh
python3 qa/seed_me_conduct.py contracts /tmp/seed-language-dogfood/final/small-replay/seed-contract.simulated.md --strict
python3 qa/seed_me_conduct.py ledgers /tmp/seed-language-dogfood/final/small-replay/sessions --strict
python3 qa/seed_me_conduct.py ledgers /tmp/seed-language-dogfood/final/hard --strict
```

An initial root call to the replay parent directory found zero ledgers. That was
not accepted as validation; the corrected `sessions` path above checked one.
The incomplete hard-stop contract is not presented as a completed contract and
was not subjected to completion-format checks.

Limits: the same isolated operator was reused; the hard stop was specified in its
persona; the small interview had no remaining consequential option choice after
its goal reply. Its first publication omitted the rejected draft options, although
the transcript retains them. We make no claim that every instruction was followed
perfectly. Dogfood viewers were checked through HTTP and status, without visual
inspection; separate automated browser tests passed. Earlier mistakes and record
repair remain part of the evidence. No human usability evidence was collected.

Full raw evidence, including failed attempts, exact command outputs, session
history, and HTML snapshots, is retained locally at `/Users/jondev/.codex/artifacts/seed-me-language-2026-10-02-4hwihtk3`. Temporary paths
in the copied transcripts identify the original execution locations; the archive
contains the same artifacts under `examples/` and `dogfood/`. These are one-time
trial artifacts, not a permanent evaluation framework.
