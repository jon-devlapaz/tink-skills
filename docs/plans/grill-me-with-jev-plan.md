# Build plan: grill-me-with-jev hardening

Inputs: [intent](../intent/grill-me-with-jev-intent.md),
[spec](../specs/grill-me-with-jev-spec.md). User requested local remediation.

## Sequence

1. Capture baseline behavior with a fresh, read-only evaluator before editing the
   contract. Preserve the original six-test result as structural evidence only.
2. Define fixed adversarial evaluation inputs and acceptance criteria covering
   R1-R10 before making the contract changes.
3. Revise `skills/grill-me-with-jev/SKILL.md` and its triage reference. Keep a concise
   workflow and one source of truth for transition and provider details.
4. Replace wording-presence tests with structural/link/fixture checks. Run the full
   Python test suite and the available skill metadata validator.
5. Run independent evaluations against the revised skill, inspect failures, fix the
   contract, and repeat affected cases without weakening the expected outcomes.
6. Record results, residual limitations, and a repeatable maintenance procedure in
   `docs/reviews/grill-me-with-jev-review.md`.

## Scope and risk

Existing skill, intent, spec, and tests are untracked user workspace content;
update them in place without staging or committing. New evaluation and review
artifacts belong to this change. Do not install providers, use live credentials,
modify global policy, publish, or create a PR.

The main risk is adding enough state detail to obscure the interview workflow.
Keep the core short and put conditional mechanics in its required reference.

## Proof and maintenance

Run `python3 -m unittest discover -s tests -v` and the skill creator's
`scripts/quick_validate.py skills/grill-me-with-jev` when its dependencies exist.
Read-only fresh-agent evaluation is the behavioral check; no synthetic Python
state machine will be presented as proof of an LLM's behavior. Keep the scenarios
stable across revisions. New incidents add cases; skill/model changes rerun the
suite and compare critical failures and repeated-question counts before release.

## Execution result

Completed all six steps. See the [review evidence](../reviews/grill-me-with-jev-review.md)
for baseline failures, independent case outcomes, targeted corrections, test
results, and the final review. No release or human approval is implied.
