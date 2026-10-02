# Paired output samples

These are synthetic output samples, not executed interviews. The same sampler
saw both versions; only the later review was blinded. Inputs are in `cases.json`.
The evidence quoted as `/tmp/seed-language-eval/fixture.txt` is copied here unchanged
as `fixture.txt`. `{LEDGER_URL}` is a supplied placeholder, not a live viewer.

## Before

# Baseline output samples

Recorded from unchanged canonical Seed Me instructions before edits. This is one agent's output sampling with inspected synthetic evidence, not a completed interview, dogfood lifecycle run, simulated-operator session, or human usability study. No source files were edited. {LEDGER_URL} is a supplied scenario placeholder, not a running service. Fixture claims describe only the invented example; no product behavior was verified.

Sources read: SKILL.md, lean-path.md, ledger-transitions.md, agent-mode.md, nasa-spike/PROMPT.md, qa/README.md. NASA material is prior research only. qa README prescribes no evidence directory; its docs/seed-me-qa-plan.md link points to an absent docs directory.

## rough

Input: Seed this: I keep losing useful notes. Maybe a local thing that helps me find them? I am not sure what it should do.

Context: No confirmed goal, no session. Do not inspect unrelated files. Shape an initial working draft only.

### Output

Working draft
- PROVISIONAL goal: Help you find useful notes you have already saved.
- PROVISIONAL outcome: A local helper that finds relevant notes without editing them.
- PROVISIONAL option A: Search by words — simple, but you need to remember useful words.
- PROVISIONAL option B: Browse grouped notes — less typing, but useful groups need to be worked out.

What should we keep, cut, or reshape?

## technical

Input: I confirmed the goal: decide how this importer should handle existing notes. What should happen when an incoming ID already exists?

Context: Active Full question turn; one ready decision, none waiting. Inspected fixture lines 3-4. The two real choices are keep replacement with preview or reject matching IDs. Owner: note owner. No decision has been made. Reversal is cheap. Do not claim reject mode already exists.

### Output

Question 1 of 1 ready (0 waiting on earlier answers)
❓ Matching note IDs: Should an import replace an existing note or reject the incoming match?
📜 What I found: "Import uses ON CONFLICT (id) DO UPDATE to replace matching note content." (/tmp/seed-language-eval/fixture.txt:3, observed this session)
📜 What I found: "Preview shows each matching ID and both versions before import." (/tmp/seed-language-eval/fixture.txt:4, observed this session)
Option A: Keep replacement with preview — tradeoff: updates existing notes but can replace text you want to keep. If you pick B instead: incoming matches are rejected. Undo cost: cheap.
Option B: Reject matching IDs — tradeoff: preserves existing notes but prevents updates through import. If you pick A instead: you can replace notes after preview. Undo cost: cheap.
👤 Owner: note owner — Gate: choose replacement or rejection — Why it matters: determines whether imports may overwrite existing content.
Against my suggestion: Rejecting matches prevents accidental replacement even when someone misses a preview difference.
➡️ My suggestion: A, because the existing behavior already provides a preview. Confidence: medium.
   Observed: replacement and preview exist. Inferred: updating existing notes is useful. Would flip if: preserving existing text matters more than importing updates. Not checked: whether preview is mandatory. My number to change: none.
Ledger: {LEDGER_URL}

## assumption

Input: Use the local helper idea. We have not discussed how to order search results.

Context: Confirmed goal in active Lean session: find notes on one machine without editing them. Inspected fixture line 2. The default result order has no meaningful effect on implementation, risk, cost, reversibility, or behavior in this scenario. Record alphabetical order as an assumption only; no question needed.

### Output

I'll assume these unless you object
- List results alphabetically. This is an assumption, not your answer; the order is easy to change.

📜 What I found: "The local note helper reads one folder and never writes source files." (/tmp/seed-language-eval/fixture.txt:2, observed this session)
Ledger: {LEDGER_URL}

## recommendation

Input: Should this importer ask me before each import or run automatically?

Context: Active Full question turn; one ready decision, none waiting. Inspected fixture lines 5-7. User has explicitly said: I care more about checking each change than saving clicks. Both choices are feasible and cheap to undo. Owner: note owner. No choice has yet been made.

### Output

Question 1 of 1 ready (0 waiting on earlier answers)
❓ Import review: Should each import wait for your click or run automatically?
📜 What I found: "Review mode requires a user click before each import." (/tmp/seed-language-eval/fixture.txt:5, observed this session)
📜 What I found: "Automatic mode imports all matching IDs without individual review." (/tmp/seed-language-eval/fixture.txt:6, observed this session)
📜 What I found: "Both modes have a tested restore command for the previous import." (/tmp/seed-language-eval/fixture.txt:7, observed this session)
Option A: Review each import — tradeoff: you can check every change, but must click each time. If you pick B instead: matching IDs import without review. Undo cost: cheap.
Option B: Import automatically — tradeoff: fewer clicks, but changes happen before you inspect them. If you pick A instead: each import waits for you. Undo cost: cheap.
👤 Owner: note owner — Gate: choose review or automatic import — Why it matters: decides whether changes wait for your review.
Against my suggestion: Automatic import removes repeated clicks and the fixture reports a restore command.
➡️ My suggestion: A, matching your stated preference to check each change. Confidence: high.
   Observed: both modes and the fixture's restore claim. Inferred: review still matters more to you than speed. Would flip if: you prefer fewer clicks. Not checked: the restore command's behavior on your real data. My number to change: none.
Ledger: {LEDGER_URL}

## hard

Input: Should we publish the customer export now?

Context: Active Full question turn; one ready decision, none waiting. Inspected fixture lines 8-9. Owner: data owner. Publishing is hard to undo; retaining private access is feasible. No instinct or request to show the recommendation has been supplied. Do not show options or recommendation yet.

### Output

Question 1 of 1 ready (0 waiting on earlier answers)
❓ Publish the customer export: Should customer email addresses become available in a download that recipients can copy?
📜 What I found: "The shared export includes customer email addresses." (/tmp/seed-language-eval/fixture.txt:8, observed this session)
📜 What I found: "A published download can be copied by its recipients." (/tmp/seed-language-eval/fixture.txt:9, observed this session)
👤 Owner: data owner — Gate: explicit choice about publication — Why it matters: copies can remain after you remove the download.
What's your instinct?
Ledger: {LEDGER_URL}

## stop

Input: Stop the interview. Give me what you have.

Context: Active Full session, goal confirmed; unresolved blockers are overwrite policy and proof of independent backup. Inspected fixture lines 3 and 10. No contract revision displayed or confirmed. This is output-only: lifecycle operations are not run; describe what must still be done instead of claiming a saved snapshot or server shutdown.

### Output

Status: stopped — incomplete.

The overwrite policy is undecided, and an independent backup has not been verified. These remain blockers. There is no confirmed seed contract to hand off and no implementation approval.

This output sample has not ended a session or saved a view. In a real session, the host must end it as stopped, preserve the blockers, save and verify the read-only view, and stop its recorded viewer process. Report any failure; do not claim those steps succeeded without checking.
Ledger: {LEDGER_URL}

## Invariant assessment

| Case | Decision pacing | Evidence/source | Meaning/authority | Consequences/owner | Hard choice | Unsupported claims/blockers | Operations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rough | One draft reaction | Draft exemption | All proposed content provisional | Draft options tradeoffs; no settled solution | N/A | No invented settled answer | No session before confirmation |
| technical | One decision | Inspected fixture lines 3-4 | Inference and unchecked preview rule visible | Two real choices, note owner | Cheap per scenario | Reject mode is an option, not claimed existing | Link retained; lifecycle not exercised |
| assumption | No unnecessary decision | Fixture line 2 | Assumption explicit | N/A | N/A | No accepted answer invented | Lifecycle not exercised |
| recommendation | One decision | Fixture lines 5-7 + supplied preference | Recommendation remains a proposal | Both choices, note owner | Cheap per scenario | Restore is fixture claim, not real-data verification | Link retained; lifecycle not exercised |
| hard | One decision | Fixture lines 8-9 | No recommendation or decision | Data owner; options withheld | Instinct first | Copy consequence disclosed | Link retained; publication not exercised |
| stop | No question | Sources in context; blocker summary retained | No confirmation or approval | Blockers preserved | N/A | Does not claim executed shutdown | Required end/save/verify/stop explicit; not executed |

Assessment is manual and limited to these outputs. Operational correctness requires a separate actual session run. Current template repeats consequences in both option rows and packs five caveats onto a long line. Those are concrete candidates for simplification; their information must remain available. The hard-choice instructions simultaneously say "show only the question and what you found" and require every question to name its owner/gate and ledger. This baseline retains owner and ledger; consolidation should make that exception explicit.


## After

# Revised output samples

Same cases.json inputs, contexts, synthetic fixture, sample scope, and unchanged model context as baseline. No explicit output limit in either pass; each was given the same six-case task. The sampler saw its earlier outputs, so this is not blind generation. No session lifecycle or simulated operator was run. No human usability claim follows.

## rough

Input: Seed this: I keep losing useful notes. Maybe a local thing that helps me find them? I am not sure what it should do.

Context: No confirmed goal, no session. Do not inspect unrelated files. Shape an initial working draft only.

### Output

Working draft — all points below are PROVISIONAL assumptions.
- Goal: Help you find useful notes you have saved.
- Outcome: A local helper that finds notes without changing them.
- Option A: Search by words. Simple to use, but you need useful search words.
- Option B: Browse groups of notes. Less typing, but we need to decide how to group them.

What should we keep, cut, or reshape?

## technical

Input: I confirmed the goal: decide how this importer should handle existing notes. What should happen when an incoming ID already exists?

Context: Active Full question turn; one ready decision, none waiting. Inspected fixture lines 3-4. The two real choices are keep replacement with preview or reject matching IDs. Owner: note owner. No decision has been made. Reversal is cheap. Do not claim reject mode already exists.

### Output

Question 1 of 1 ready (0 waiting on earlier answers)
❓ Matching note IDs: Should an import replace an existing note or reject the incoming match?
📜 What I found: "Import uses ON CONFLICT (id) DO UPDATE to replace matching note content." (/tmp/seed-language-eval/fixture.txt:3, observed this session)
📜 What I found: "Preview shows each matching ID and both versions before import." (/tmp/seed-language-eval/fixture.txt:4, observed this session)
Here, ON CONFLICT means the importer found an existing note with the same ID.
Option A: Keep replacement with preview — allows updates, but can replace text you want to keep. Undo cost: cheap.
Option B: Reject matching IDs — protects existing text, but prevents updates through import. This would change the current behavior. Undo cost: cheap.
👤 Owner: note owner — To decide: choose replacement or rejection — Why it matters: imports may overwrite existing content.
Against my suggestion: Rejecting matches protects notes even if someone misses a preview difference.
➡️ My suggestion: A, because replacement already has a preview. Confidence: medium.
   Checked: replacement and preview exist. Inference: preview may help you spot unwanted changes.
   Assumptions: importing updates is useful to you. Not checked: whether preview is required.
   I would change my suggestion if: preserving existing text matters more than importing updates. Proposed number: none.
Ledger: {LEDGER_URL}

## assumption

Input: Use the local helper idea. We have not discussed how to order search results.

Context: Confirmed goal in active Lean session: find notes on one machine without editing them. Inspected fixture line 2. The default result order has no meaningful effect on implementation, risk, cost, reversibility, or behavior in this scenario. Record alphabetical order as an assumption only; no question needed.

### Output

I'll assume these unless you object
- List results alphabetically. You have not confirmed this order. It is easy to change.

📜 What I found: "The local note helper reads one folder and never writes source files." (/tmp/seed-language-eval/fixture.txt:2, observed this session)
Ledger: {LEDGER_URL}

## recommendation

Input: Should this importer ask me before each import or run automatically?

Context: Active Full question turn; one ready decision, none waiting. Inspected fixture lines 5-7. User has explicitly said: I care more about checking each change than saving clicks. Both choices are feasible and cheap to undo. Owner: note owner. No choice has yet been made.

### Output

Question 1 of 1 ready (0 waiting on earlier answers)
❓ Import review: Should each import wait for your click or run automatically?
📜 What I found: "Review mode requires a user click before each import." (/tmp/seed-language-eval/fixture.txt:5, observed this session)
📜 What I found: "Automatic mode imports all matching IDs without individual review." (/tmp/seed-language-eval/fixture.txt:6, observed this session)
📜 What I found: "Both modes have a tested restore command for the previous import." (/tmp/seed-language-eval/fixture.txt:7, observed this session)
Option A: Review each import — lets you check changes first, but needs a click each time. Undo cost: cheap.
Option B: Import automatically — saves clicks, but changes happen before you inspect them. Undo cost: cheap.
👤 Owner: note owner — To decide: choose review or automatic import — Why it matters: changes either wait for you or happen without review.
Against my suggestion: Automatic import saves repeated clicks, and the fixture reports a restore command.
➡️ My suggestion: A. You said checking each change matters more than saving clicks. Confidence: high.
   Checked: the fixture describes both modes and a restore command. Inference: review fits your stated preference.
   Assumptions: none beyond the supplied scenario. Not checked: restore behavior on your real data.
   I would change my suggestion if: you prefer fewer clicks. Proposed number: none.
Ledger: {LEDGER_URL}

## hard

Input: Should we publish the customer export now?

Context: Active Full question turn; one ready decision, none waiting. Inspected fixture lines 8-9. Owner: data owner. Publishing is hard to undo; retaining private access is feasible. No instinct or request to show the recommendation has been supplied. Do not show options or recommendation yet.

### Output

Question 1 of 1 ready (0 waiting on earlier answers)
❓ Publish the customer export: Should customer email addresses be available in a download that recipients can copy?
📜 What I found: "The shared export includes customer email addresses." (/tmp/seed-language-eval/fixture.txt:8, observed this session)
📜 What I found: "A published download can be copied by its recipients." (/tmp/seed-language-eval/fixture.txt:9, observed this session)
👤 Owner: data owner — To decide: explicitly choose whether to publish — Why it matters: removing the download cannot remove recipients' copies.
What's your instinct?
Ledger: {LEDGER_URL}

## stop

Input: Stop the interview. Give me what you have.

Context: Active Full session, goal confirmed; unresolved blockers are overwrite policy and proof of independent backup. Inspected fixture lines 3 and 10. No contract revision displayed or confirmed. This is output-only: lifecycle operations are not run; describe what must still be done instead of claiming a saved snapshot or server shutdown.

### Output

Status: stopped — incomplete.

The overwrite policy still needs a decision. We have not verified an independent backup. Both remain blockers. There is no confirmed seed contract to hand off, and implementation is not approved.

This is an output sample. No session was ended or saved. The host still must end the session as stopped, keep the blockers, save and check its read-only view, and stop only its recorded viewer process. The host must report any failure. The note owner must choose the overwrite policy, and the host must check the backup before a future handoff can be confirmed.
Ledger: {LEDGER_URL}

## Per-case invariant assessment

| Case | One decision | Evidence | Meaning and authority | Options and owner | Instinct first | Claims and blockers | Required operations |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rough | One draft reaction | Draft exemption | Whole block provisional | Two candidate approaches, neither accepted | N/A | No goal confirmation invented | No session before confirmed goal |
| technical | One | Exact fixture quotes and paths | Checked facts, inference, assumption, unchecked requirement separate | Two consequential options, note owner, explicit answer needed | Cheap per context | Reject option explicitly changes current behavior | Footer retained; operations not run |
| assumption | No unnecessary question | Exact fixture quote and path | Alphabetical order not confirmed | N/A | N/A | No assumed user answer | Operations not run |
| recommendation | One | Exact fixture quotes and paths | Suggestion separate from stated preference and real-data uncertainty | Review/automatic costs, note owner, explicit choice | Cheap per context | Fixture restore statement not real-data verification | Footer retained; operations not run |
| hard | One | Exact fixture quotes and paths | No suggestion or accepted decision | Data owner named; options intentionally withheld | Yes | Copy consequence preserved | Footer retained; operations not run |
| stop | No question | Facts carried from supplied context | No confirmed handoff or approval | Note owner and host next actions named | N/A | Both blockers retained, no false saved state | End, preserve, save, verify, stop recorded process, report failure remain explicit |

No critical semantic or authority error found by the sampler. This judgment needs independent review. The final hard-choice instruction explicitly retains evidence, owner, answer needed, and ledger; this matches the generated output. Comparison limitations: six synthetic examples, same sampler saw baseline, no randomized repeat generations, no lifecycle testing here. The stop sample's note-owner assignment follows the note-import context; it is a proposed role for the remaining choice, not a newly settled decision.
