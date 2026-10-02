# Seed Me dogfood

## Final runs

- Small idea: `/tmp/seed-language-dogfood/final/small-clean/`. A separate operator agent gave the goal, answered each of the three probes in a separate turn, saw the full contract, gave a teach-back, then separately affirmed the displayed revision as a simulation. The session ended `completed`; the contract remains `simulated — not confirmed by a human`. Strict contract checks passed. No implementation occurred.
- Hard-to-undo decision: `/tmp/seed-language-dogfood/final/hard/`. The question included evidence, owner, answer needed, and ledger link. It withheld options and recommendation. The operator stopped; the session ended `stopped` with the deletion decision unresolved. The incomplete simulated contract preserves that blocker. Stop prevented close probes and teach-back; they were not claimed as completed.
- Both real ledger lifecycles started after their goal replies. Both owned viewers returned live HTML, served the ended state, saved current snapshots, and were stopped. Follow-up socket checks refused connections. Every settled answer has simulated authority; no user or delegated authority was used.

## Evidence

- `final/small-clean/transcript.json` and `transcript.md`: final interview text and replies. The displayed contract is embedded verbatim. `seed-contract.simulated.md` adds only the later simulated affirmation record.
- `final/hard/transcript.json` and `transcript.md`: risky scenario, instinct-first question, stop, and stop summary.
- `commands.log`: exact session.py commands, return codes, stdout and stderr.
- `final/verification.json`: ended states, simulated authority, unresolved hard blocker, absent recommendations, current snapshots and closed ports.
- `final/small-clean/contract-check.json`: exact strict contract-check command, exit code 0 and output.
- `final/small-clean/count-evidence.json`: explicit count inputs. Command computed 0 accepted unchanged of 2 draft options, 1 operator scope-and-wording choice, contract revision 1.
- `final/skill-hashes.txt`: final source hashes read before these runs. No source edits were made by this agent.
- Each final run includes its actual session directory, ledger, history, snapshot, fetched live-start HTML and fetched live-ended HTML.

## Failures and corrections

- Initial setup under `small/` initialized before the goal reply and read the Full ledger reference while preparing Lean. It was stopped, with no decisions published. These were host-procedure failures.
- A run under `small-valid/` was stopped after the skill changed. Another finished run under `preliminary/` predates the final owner-wording edit. They are not final evidence.
- `final/small/` bundled three probes in one turn and used shortened Knowledge map labels that failed the strict check. It also did not separate simulated affirmation from teach-back. It remains a failed preliminary attempt. The clean final rerun corrects these issues.
- The clean final draft initially used a curly apostrophe in “What we know we don’t know”; the strict checker required the template’s straight apostrophe. Corrected before displaying the full contract; final check passes. The initial checker output remains in the tool transcript, not the final pass artifact.
- The final small session’s first publication used an empty draft-options array although the chat draft presented fixed/editable options. The selected goal and actual choices were preserved. This is a record-completeness limitation, not evidence that all instructions passed.

## Limits

These are real simulated interview operations, not response samples alone, human usability evidence, or human approval. The same isolated operator agent was reused with a new persona brief for the hard scenario and then the final small rerun; it retained prior interview messages, but received no skill text, ledger contents, tool outputs, or internal notes. No operator tools were observed. Hard-stop behavior was requested in its persona, so the run checks handling of a stop, not whether an unbiased operator would choose it.

The small case had no unresolved consequential choice after the operator supplied exact wording. It therefore tests short drafting, probes, contract review, simulated affirmation, and lifecycle—not a cheap-choice recommendation turn. The hard case uses a clearly labeled synthetic fixture, not actual backups. No product files or real essays were provided; product/repository review and real-use verification were out of scope. No recoverability probe applied to the small file-creation proposal. The transcript states the close review and unknowns; it does not establish real-world usefulness.

Browser rendering was not visually inspected. HTTP content and session status were verified. Opening a browser was omitted because this run used shell-only HTTP verification; this is a recorded limitation. The process handles stopped by the harness were 85739 (preliminary), 94299 (failed pacing), 48478 (hard), 1335 (clean small), and 38046 (superseded setup); all stops returned exit code 0.

## Later strict ledger finding and repair replay

The final interactive small run failed the strict ledger source check: P1, P2, P3, T1, and R1 retained the exact simulated words but omitted quote delimiters in authority_source. The original ended ledger remains unchanged and is retained as failed formatting evidence.

`final/small-replay/` is a fresh artifact-validation replay of the retained transcript and original publication history, not a new interview or independent usability result. It republishes the same choices with quoted simulated replies and transcript provenance. Its strict ledger check passes all three checks (exit 0); the semantic node comparison passes after excluding authority_source and helper history/revision. The replay exercised init, seven publications, viewer start, completion, live ended-state fetch, snapshot, owned-process shutdown, and closed-port verification. It still grants no human confirmation or implementation authority.

Exact replay commands/results: `final/small-replay/commands.jsonl`; retained inputs: `replay-states.json`; strict results: `strict-ledger-check.json`; original failure: `original-ledger-check.json`; closure and semantic comparison: `verification.json`. The replay viewer used process handle 57007 and stopped with exit 0.
