# Seed contract: essay checklist
status: simulated — not confirmed by a human
operator: simulated
revision: 1
date: 2026-10-02

## You are confirming
- Goal: remember to read the title and opening paragraph before sending an essay.
- What gets built: a plain text file saying “Read the title” and “Read the opening paragraph.”
- What does not: apps, automatic checks, or checks of other sections.
- Accepted unchanged: 0 of 2 draft options; chosen by the operator: 1 scope-and-wording choice.
- Still unknown: whether a real writer would remember to use it. No earlier decision is reversed.

## Now
- Settled: the simulated goal and wording.
- Uncertain: real usefulness and the file location.
- Needs you next: explain the proposal in your own words. A human must review before adoption.

## Goal
G [simulated] Make a plain text checklist for the title and opening paragraph before sending an essay.

## Decisions
D1 [simulated] Use the operator’s exact reminders, without automation. Source: “I want a plain text file with ‘Read the title’ and ‘Read the opening paragraph’; skip the extra choices and automation.”

## Assumed (not confirmed by you)
S1 [agent] Use UTF-8 plain text — why it is safe to assume for this proposal: changing it is easy.

## Constraints and exclusions
C1 [simulated] Do not add other checks. Source: “I’d be surprised if it asked me to check anything beyond the title and opening paragraph.”

## Acceptance checks
A1 [agent] The file contains exactly the proposed reminders.
provisional: the checklist file must exist before this proposed check can run.
cmd: `python3 -c "from pathlib import Path; assert Path('essay-checklist.txt').read_text().splitlines() == ['Read the title','Read the opening paragraph']; print('PASS')"`
expect: `PASS`
cwd: a folder chosen by the human owner before implementation.
This command has not run. It is a proposed check, not completed verification.

## Open questions
Q1 [agent] File location is a non-blocking deferral — owner: the human owner — revisit: before implementation. Location does not change the proposal. No active interview blocker remains in the simulation.

## Knowledge map
- **What we know, with proof:** E1 records simulated preferences, not human decisions or machine facts; observed 2026-10-02; re-check with the real owner before adoption.
- **What we know we don't know:** whether the checklist helps; the human owner can assess it after authorizing creation.
- **What we have not read:** no essay or existing checklist was supplied. We did not inspect product repositories, reviews, or notes because none were part of this hypothetical request. The human owner reads their essay when using the checklist.
- **What could surprise us:**
  Probe: Imagine this checklist turns out unhelpful. What is the most likely reason? — answer: “I might forget to open the checklist before sending the essay.” — changed: recorded forgetting as a risk.
  Probe: Give me one case where this checklist should not apply, or that would surprise you. — answer: “I’d be surprised if it asked me to check anything beyond the title and opening paragraph.” — changed: reinforced the scope; no new feature.
  Probe: What would another writer who uses checklists ask that we have not? — answer: “I don’t know what another writer would ask; I’d just like to see the two-line checklist.” — changed: nothing; the outside view remains unknown.
  Where we did not look: other writers, essays, editing tools, or repeated real use.
  We would know we were wrong if: the owner still forgets either section despite trying the checklist.

## Evidence
E1 [simulated] The quoted operator replies above are simulation evidence only, observed 2026-10-02. Grounded in: operator transcript. No product files inspected or created. No repeat surprise was cited.

## Review, risks, and next steps
I checked this draft for missing decisions and contradictions. Goal coverage stays within the requested reminders. Forgetting to open the file is an unresolved practical risk. No security, deletion, replacement, or recovery action is proposed. No recoverability probe applies. Nothing has been built or tested. Agent teach-back is weak evidence because the agent sees this draft; a human still owes their own explanation before adoption.
The human owner must decide whether to adopt this proposal through a normal session and later authorize implementation. The ledger is an interview record; this contract is the proposed handoff. It is not human-confirmed and grants no implementation permission.

## Simulated response to revision 1
The operator said: “Yes, that matches what I want: a plain text file with those two reminders.” This is a simulated answer, not human confirmation. Teach-back matched the scope; the human still needs to review and explain the proposal before adoption.
