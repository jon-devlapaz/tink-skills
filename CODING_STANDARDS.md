# Coding standards

Read during review. A reviewer applies every rule to the diff and reports each violation with file and line. Mechanical checks live in the test suite (`python3 -m unittest discover -s tests`), not here.

## Skill text

**One outcome per branch.** Each decision point in a SKILL.md or reference ends in one deterministic outcome. Two rules that govern the same trigger (a no-qualifier escalation here, an insufficiency broadening there) need one condition. Ranking criteria in an overflow rule are the final ranking criteria, with source position and query rank as tie-breakers.

**Gates agree with defaults.** A quiet default ("headless unless asked") also resolves the question order and the completion criterion that mention that choice. Read the whole file for each gate the change touches.

**Restatements move together.** When a mode list, flag, outcome name, or command changes, search the README, SKILL.md, references, and tests for every copy. Example: `ABSTAIN/BUILD` is an outcome in skill-scout; a README that lists it as a mode is wrong.

**Claims match the preview.** A README says users inspect what the dry run actually returns. Spend counts say "harness invocations", with model calls labelled unknown, unless a cap enforces exact calls.

## Tests for skills

**Grade the behavior.** A check that fails a compliant answer (rejecting a word the answer may say while declining) tests vocabulary, not behavior.

**Production-path tests.** A test that builds its own state proves only the code after that state. A claim about a whole flow needs a test that drives the real entry point with an offline fake for anything paid or networked.
