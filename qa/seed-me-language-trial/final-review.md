# Independent follow-up review

## Conclusion

The narrow wording improvement can be kept. I found no remaining critical loss of meaning or unsupported decision authority in the six final samples. The repaired stop sample resolves both earlier concerns: it does not invent owners for the blockers, and it distinguishes stopping questions from completing the session's shutdown and saved view.

This is an independent assessment of the final wording, not a second blind comparison. I read `final-after.md`, `cases.json`, and the current worktree's `SKILL.md` and `references/lean-path.md`. I also retain the fixture and anonymized pairs read in the earlier blind review. I did not inspect the label mapping or run sessions. The final artifact's self-assessment is not my evidence that its claims are correct; the supplied contexts, fixture, and instructions are.

## Invariants by sample

| Sample | Assessment |
| --- | --- |
| rough | The whole draft is clearly provisional. The goal, nonediting behavior, and options are proposals, not accepted decisions. The user is asked to reshape the draft. No session or confirmed goal is invented. The search-versus-browse difference survives. |
| technical | Exactly one decision is presented. Exact fixture quotes and paths survive. The SQL term is explained outside the quote. Current replacement behavior is separated from proposed rejection. Both choices retain their benefit, cost, and scenario-supplied undo cost. The note owner remains the decider. The suggestion has medium confidence, a contrary argument, a labeled assumption about useful updates, an explicit unchecked preview requirement, and a condition that would change the advice. No answer or permission is invented. |
| assumption | Alphabetical order is explicitly unconfirmed and shown under the required assumption heading. The sample does not force a question about an inconsequential default. It retains the inspected source quote and does not turn the assumption into a user answer. Whether an actual ledger records it correctly is untested. |
| recommendation | The two feasible modes and their consequences remain clear. The stated preference is attributed to the supplied scenario; the recommendation does not become a decision. The restore claim remains attributed to the fixture and is expressly unverified on real data. The note owner, contrary argument, confidence, condition for changing the suggestion, evidence quotes, and ledger placeholder remain. |
| hard | The publication question, customer-email evidence, copyability consequence, and data owner remain visible. It requests the user's instinct before showing either options or a recommendation, as instructed. No publication approval is implied. Removing a hosted download does not itself remove copies held by recipients; the consequence is supported, although the earlier “copies can remain” wording is more cautious. |
| stop | Questioning is halted; the supplied session state is still active. Both blockers remain explicit. Their owners are explicitly unassigned. No confirmed contract, implementation approval, saved view, ended session, or stopped viewer is claimed. The host's duty to end as `stopped`, preserve blockers, save and verify the view, stop only the recorded viewer, and report failures remains explicit. Reporting the final stopped status and saved-view link is conditional on successful execution. |

All three actual question samples preserve one-decision pacing and the literal `Ledger: {LEDGER_URL}` placeholder. The draft, assumption, and stop samples appropriately do not force an additional decision. No sample supplies invented operator answers, settles a recommendation, claims an actual lifecycle operation, or authorizes implementation.

## Consistency with the current instructions

The final wording follows the new clear-writing rules while retaining the substantive controls in the skill:

- It distinguishes checked facts, uncertain inferences, assumptions, suggestions, and accepted decisions.
- It preserves exact quoted evidence and identifiers while explaining the necessary technical term separately.
- It states the meaningful option differences once and keeps the owner and requested answer visible.
- It keeps required actions and missing ownership visible in the stop message.
- It retains the Full question format and the hard-to-undo instinct-first rule.
- The Lean assumption remains an assumption; it grants neither acceptance nor implementation authority.

The skill's stop section says to report `stopped — incomplete`, while its lifecycle section requires actual ending, saving, verification, and viewer shutdown. In this explicitly output-only case, making that final report conditional is an honest reconciliation with the instruction not to claim unperformed operations. It does not excuse leaving those operations undone in a real session.

## Limits and small residual concerns

1. These samples do not demonstrate working session initialization, publication, persisted blockers, revision confirmation, snapshot creation, or process shutdown. The actual lifecycle also includes details such as retrying a failed save and verifying the ended view; the brief stop sample is not a replacement for those operational instructions.
2. The stop sample summarizes blocker evidence without repeating the fixture quotes. That is acceptable for a concise stop report, but it does not independently show that the ledger contains the evidence or preserved blockers.
3. The technical recommendation depends on importing updates being useful. It correctly labels that assumption and leaves the decision open; the sample does not establish that replacement is the best choice for a real user.
4. Undo costs and user preferences are supplied scenario facts, not independently measured results or actual user authorization.
5. The repaired sample is informed by review findings. The six final outputs are a targeted reassessment, not six fresh independent generations. Neither the blind wording comparison nor this follow-up establishes human comprehension, reliability across sessions, or usability improvement.

No additional source change is justified by these residual limitations alone. Keeping the wording change is supported as a narrow editorial improvement with preserved visible controls, provided the reported result remains limited to these samples.
