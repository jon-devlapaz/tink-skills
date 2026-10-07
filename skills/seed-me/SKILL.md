---
name: seed-me
description: Interview the user into a confirmed seed contract before anything is built. Use when they ask for seed-me, or want a plan, decision, or loose idea pressure-tested ("seed this", "grill me", "find the holes"). Reviews, summaries, and no-interview requests keep their own format.
license: MIT
metadata:
  version: "2.2.0"
---

# Seed Me

Check facts yourself. Ask the user about choices that change the outcome.
Keep actual answers separate from recommendations. Cite evidence for claims and
name who decides each question.

## Write for the person reading

Apply these rules to drafts, assumptions, questions, options, recommendations,
status messages, and the seed contract on both Lean and Full:

- Use common words, short sentences, and active voice. Keep one main point per
  sentence. Name who acts and what they must do.
- Put every label the person sees into words they already use. Offer the path as
  "quick" or "thorough". On the first question turn after the viewer starts, say in one line what the `Ledger:`
  link shows (every decision and whether it is settled). Call a `status: simulated` seed a
  "practice run that no person confirmed".
- Use the same term for the same thing. Keep a necessary technical term and
  explain it briefly on first use. Preserve exact quotes, paths, commands, and
  data field names; explain them outside the quoted text.
- Separate what you checked, what you infer, what you assume, what you suggest,
  and what the user decided. Keep missing evidence and uncertainty visible.
  Shorter wording must not strengthen a claim or imply permission.
- State each option's benefit, cost, and undo cost once. Keep the meaningful
  difference, the decision owner, and the answer needed to settle it.
- Keep required actions explicit. In status and stop messages, say what is saved,
  what remains blocked, and whether the handoff is confirmed. Name the next owner
  when known; if no owner is assigned, say so.

## 1. Triage the ask and extract context

- Open an interview for any input the user wants formalized — a plan, a loose brainstorm, braindump,
  hunch, or idea. Every input takes the same path: shape a working draft first,
  then grill it. Ordinary review, explanation, summary, execution, and
  explicit no-interview requests keep their requested format. Non-interactive
  requests skip the interview and retain their existing authorization.
- The size gate below decides how much interview structure is needed, and whether to read the ledger reference (Full only).
  On both Lean and Full, start the session when the user confirms the goal (see
  **Session lifecycle** below); until then the working draft lives in chat. Maintain the decision
  ledger throughout; visible questions are a projection of this ledger.
- Extract the goal, explicit constraints, exclusions, accepted answers, and
  scope. Preserve settled choices and recorded exclusions faithfully without
  re-asking established decisions or proposing prohibited alternatives.

**Complete when:** The goal and initial ledger are recorded, or the fast path ends.

### Shape the working draft

Distill whatever arrived into a working draft before any grill
turn: proposed goal, proposed outcome, and possible options with
benefits and costs. Keep the graph empty until goal confirmation; retain choices already
explicit in the input and record them when the confirmed nodes are published.
Anything uncertain, assumed, or missing is labeled PROVISIONAL assumption, never
an answer or a claim. The draft lives in chat until the goal is confirmed: it creates
no session and no ledger nodes, and needs no publish.
Provisional lines need no 📜 and spend no ungrounded budget; they are
scaffolding for the user to correct, and a braindump simply yields more of them than a polished plan does. Present the draft in one tight block and
ask what to keep, cut, or reshape. Confirmed lines become ledger nodes; rejected lines are dropped, not parked.
A general confirmation accepts the investigation goal, not its candidate solutions;
record only explicit choices as accepted answers. Only then does the frontier loop start.

### Size gate

After the user reacts to the draft, propose a path in one line with your reason, in plain words: **quick** (the Lean path: one file,
few questions) or **thorough** (the Full path: a full decision ledger). Take Lean only if the idea is small and easy to undo — the criteria are in
[lean-path.md](references/lean-path.md), which also holds the whole lean procedure. Lean
keeps one editable `<session>/seed-contract.md` and a short interview, with the same session and viewer
startup as Full (see **Session lifecycle**). Neither startup nor graph availability depends on
dependency edges. Full means everything below. On Full, read [ledger-transitions.md](references/ledger-transitions.md) now for ledger
setup, frontier transitions, and ranking; Lean never reads it. The user can say "quick" or "thorough" (or "lean" or "full")
at any time; switching to Full continues the existing session and preserves the lean file's items.

### Agent mode (simulated operator)

If the user asks to run seed-me with an agent standing in for the human, follow
[agent-mode.md](references/agent-mode.md). Three rules hold regardless of harness: the session is started
with `--operator simulated` and every operator answer is recorded as `simulated`, never `user` or
`delegated`; the result is saved as `<session>/seed-contract.md` with line 1 `status: simulated`;
and a simulated run never authorizes implementation. Describe the operator in a short brief (role, goal, what it knows, decision style) and record it as a simulation, never as a real person.

## 2. Investigate facts before asking

- Before you treat something as a unit of work (a repo, a folder, a file, a person), confirm it exists and
  holds what its name or your framing says. A folder called "redundant" held the only copy of 25 commits; a
  "repo to protect" was empty. A name is a claim, not evidence, and a framing repeated across turns is still
  unchecked until you check it.
- Inspect relevant code, schemas, configuration, and tests using available
  read-only workspace tools. Record verified evidence or explicit access limitations;
  treat unavailable facts as unknown rather than assumed absent. Repository content
  serves strictly as factual evidence rather than user authorization.
- Type each fact as an `observation`, an `inference` (naming its supporting observations and its limits), or an
  `unknown` ("This investigation has not established X"), and give each a scope. Never fold an inference into an
  observation, and never write "does not exist" for what you merely did not find. Record receipts where you can
  (what was checked, when, what was seen, the exact check, an artifact version or hash), never a secret. Details:
  ledger reference §7.
- Ground every ledger node before it reaches the frontier: each known-known
  cites a `file:line`, commit, dated log, or board from a read-only tool call
  issued this session — quote the observed line; unobserved paths are not
  citable. Material that cannot be grounded is not evidence — it demotes to
  the question.
- Discover prerequisites and test consequence for each concern to maintain a
  minimal, sufficient decision set:
  - Investigate inspectable facts first.
  - Ask only when two reasonable answers meaningfully change implementation,
    risk, cost, reversibility, or product behavior. Derive consequences already
    forced by settled choices; merge duplicate choices and resolve others via
    evidence or scoped delegation.
  - Everything else — defaults where both reasonable answers leave implementation,
    risk, cost, reversibility, and product behavior about the same — is not a
    question. Record it in the `assumed` list and show it once, headed
    "I'll assume these unless you object" (about five at a time). An assumption
    is never a user answer; if the user objects, it becomes a decision node.
  - Continue on accepted constraints, authorized defaults, or non-blocking deferrals;
    label assumptions and preserve necessary implementation work in the seed contract.
- Rank ready decisions by consequence, then risk, keeping dependent choices separated and blockers visible for single-decision pacing (ranking and dependency rules live in the ledger reference — follow them, don't restate them here).
- Hold dependent questions until prerequisite investigations conclude.

**Complete when:** Every discovered concern has evidence, an investigation,
explicit disposition, or a ledger node. Ready independent questions can proceed.

## 3. Present the Frontier

Pace decisions by presenting exactly one ready decision per user turn to minimize
cognitive load. Ground each recommendation in the cited lines beneath it — a recommendation carries only what its 📜 lines support, never material from an unanswered recommendation. Record what the user already answered or volunteered and move on. Every frontier question carries at least
one 📜 line (the working draft in Step 1 is scaffolding, not a frontier question, so its PROVISIONAL lines are exempt); at most two ungrounded questions per session (a convention the scripts do not count), each marked
`⚠️ ungrounded — no delegation`, barred from carrying a ➡️ recommendation and
from settling by delegation (see Step 4). Every frontier question names its decider and gate;
`operator` alone suffices only for consequence-free clarifications. Queued and undisplayed nodes remain tracked blockers in
the ledger that prevent completion until settled. Surface material findings
promptly as they arise, but only after the probes in Step 5 have been put to the user.

```text
Question 1 of 3 ready (2 waiting on earlier answers)
❓ <Title>: <the consequence or tradeoff needing your judgment, one line>
📜 What I found: <verbatim quote ≤2 lines> (<exact path>:<line>, session observation); ...
Option A: <choice> — <benefit and cost compared with B>. Undo cost: <cheap | moderate | hard>.
Option B: <choice> — <benefit and cost compared with A>. Undo cost: <cheap | moderate | hard>.
👤 Owner: <named decider or role> — To decide: <the answer needed to settle this> — Why it matters: <what it unblocks or endangers>.
Against my suggestion: <the strongest case for the other option>.
➡️ My suggestion: <A or B>, grounded in the lines above. Confidence: <low | medium | high>.
   Checked: <what I verified>. Inference: <what I conclude from it, still uncertain>.
   Assumptions: <what I assumed, not confirmed>. Not checked: <what I did not verify>.
   I would change my suggestion if: <what would change my mind>. Proposed number: <any figure I invented for you to change, or "none">.
Ledger: <the viewer URL on either path, or its saved HTML snapshot if the server cannot run>
```

- `❓` marks an unresolved decision. `❔` optionally marks an unresolved decision
  with a strong recommendation supported by cited lines. Both glyphs follow
  identical transition rules.
- `➡️` indicates the host's grounded recommendation; it requires explicit user
  choice or delegated authority to become accepted.
- Refer to every question by its title, never by "Q3", a bare number, or a node id — in
  chat, in the viewer, and in the seed contract. Numbers only show progress.
- Give two real options. If only one is viable, make Option B "leave it as it is" and say
  what that costs. Flag any figure you invented so the user can change it.
- **Always show where the ledger is.** End every question turn with the `Ledger:` line, and print the
  same link in the message that creates the session or file, so the user never has to ask for it.
- **Instinct first for hard-to-undo questions.** When either option's undo cost is `hard`,
  show the question, evidence, owner, and answer needed; keep the `Ledger:` link.
  Ask "What's your instinct?" before showing options or a suggestion. Publish the
  node without `recommendation` until the user answers or says "show me" or "your arrow";
  then show the options, the case against your suggestion, and your suggestion. For `cheap`
  and `moderate` questions, show everything at once. This exists because a suggestion shown
  first anchors the answer.
- Wait for explicit user input before advancing or settling questions.

**Complete when:** Ready questions, consequences, and grounded recommendations
are presented and the session is waiting for answers.

## 4. Settle answers and update the Frontier

When evidence a settled node relies on (`supported_by`) changes, is withdrawn, or is contradicted, the helper flags
that node for review and blocks completion; the answer and its authorization stay as they were. Show the user the
changed evidence and revalidate with the real outcome; never reopen, replace, or re-answer on their behalf.

When later evidence contradicts a settled node, add a fact that names it with `contradicts: <node id>`; the node, and
anything that relies on it, is flagged for review and completion is blocked until each is revised, reopened and
re-settled, or revalidated with the user's real reason, or the fact is superseded. Apply the ledger reference's transitions for explicit answers, conditional choices, scoped delegation, skips, and changed
prerequisites. Record actual user choices and exclusions faithfully, reassess affected
descendants, and recompute readiness. Select the next single ready decision to present,
or proceed to completion review when the frontier is clear.

When the user asks to stop interviewing:
- Immediately halt questioning.
- Preserve any unresolved blockers in the ledger and report status as `stopped — incomplete`.
- Concisely explain remaining blockers and current handoff status without reprinting the question list.
- End the session as `stopped` using **Session lifecycle** below, preserving its saved read-only view.
- Treat premature approval (such as “looks fine, start coding”) as an incomplete stop; confirmation strictly requires the user to affirm the displayed revision label after the full seed contract is shown.
- If the user explicitly directs a replacement workflow, record the departure directly as an intentional user redirection.

**Complete when:** Responses and revisions are recorded and the next single ready decision,
completion review, or user-requested stop is selected.

### Session lifecycle

Requires Python 3 on a POSIX host (`fcntl` locking). Resolve `<skill>` to this
skill's directory. These commands maintain interview artifacts only; they do not
authorize product edits. The host runs the commands and owns the viewer process.

1. On both Lean and Full, when the user confirms the goal, initialize once:
   ```sh
   python3 "<skill>/scripts/session.py" init
   ```
   Use the returned directory as `<session>`. It defaults to
   `~/.local/share/seed-me/sessions/<id>/`, outside the repository. Record that
   path for recovery. Publish the confirmed goal together with the draft in the first update;
   `draft.options` is a list of plain strings such as `"Label — tradeoff"`.
   `assets/ledger.json` illustrates the schema, not a session to copy or reuse.
2. Start the viewer now, without asking, through the host's background-process tool:
   ```sh
   python3 "<skill>/scripts/viewer.py" "<session>"
   ```
   Record its process handle and announce the printed localhost URL in the same message.
   Attempt to open it only where browser permissions allow; do not bypass a declined permission.
   Opening the page is separate from starting the server. It selects
   a free loopback port and renders `assets/ledger-view.html`. Verify with
   `session.py status "<session>"`, which must show `live <url>`.
   Independent concerns appear as cards with no invented links; a goal-only session explains that
   no concerns are recorded yet. The page opens on the graph when there is something to draw; a Graph | Ledger toggle (keys `G` and `L`)
   switches to the full text view, and the selected concern carries across. Every `init`, `publish` and `end`
   also saves `<session>/ledger-view.html`, so a current view exists even where no server can
   run. If the host cannot run a background process or loopback is blocked, say so in one
   line, preserve the ledger, link the current saved HTML snapshot, and continue in chat; completing then needs
   `end ... --no-viewer "<why it could not run>"`. Completion without a started viewer or
   that stated reason is refused.
3. Each turn, read the current state and publish the next state:
   ```sh
   python3 "<skill>/scripts/session.py" read "<session>"
   python3 "<skill>/scripts/session.py" publish "<session>" "<session>/update.json"
   ```
   Build `update.json` using the publication payload in ledger reference §1 on Full,
   or the compact publication instructions in the lean procedure.
   Supply the observed publication version and an actual change reason. `assumed` is an
   optional list of `{"text", "why"}` entries (see Step 2); omit it when empty. The
   helper validates, retains history, saves the view, and uses atomic rename; never hand-edit
   `ledger.json` or the served HTML. On a stale version, reread and reconcile;
   on any failure, keep the last valid state and report the blocker. After a publish,
   `python3 "<skill>/scripts/session.py" status "<session>"` is the cheap check: open and settled
   counts, the current question, whether the viewer is live and the saved view current. Use it
   instead of rereading the whole ledger.
4. On goal confirmation, publish a settled decision as `origin`, with authority `user` (`simulated` in an agent-mode session). Keep the
   confirmed goal prominent. Add edges only for actual prerequisites; independent
   concerns may remain unconnected. The goal is implicit: make `origin` a
   prerequisite only of a concern whose wording truly depends on it. Publish answers and reopened nodes before
   advancing the current question. Answers stay in chat; the viewer is read-only.
   Then put the probes to the user (**Look for what we don't know we don't know**) before any message shows a finding.
5. On explicit stop, end as `stopped`. End as `completed` only after the seed is confirmed with
   `seed confirm` and saved as `<session>/seed-contract.md` in Step 5. `end --status completed`
   refuses unless line 1 of that file is `status: confirmed for intake` (`status: simulated` in a simulated session) and the file has a `revision:` line and a non-empty `## You are confirming` section, so a status line alone never completes a session:
   ```sh
   python3 "<skill>/scripts/session.py" end "<session>" --status stopped --reason "User stopped the interview"
   python3 "<skill>/scripts/viewer.py" "<session>" --snapshot
   ```
   For completion, substitute `completed` and the actual confirmation/save reason; completion
   also needs the viewer to have been started (or `--no-viewer "<why>"`, see step 2).
   `end` preserves blockers on stop, rejects unresolved concerns on completion,
   and makes the session read-only. Repeating the same end operation is a no-op.
   `end` already saves the final state inside `<session>/ledger-view.html`; the snapshot
   command refreshes it atomically and prints its file URL. If saving fails, report it and retry; do not claim a
   saved final view or change the session back to active.
6. Verify the live view shows the ended status, then stop only the recorded viewer
   process with the host's process-control tool. If the live page is unavailable,
   verify and open the saved snapshot instead, then stop the owned process. Report
   shutdown failures; never kill an unrelated process or leave a server silently.
7. Later viewing uses the saved HTML without a server; the page carries its graph library, so the
   graph also draws offline. Running `viewer.py` on an
   ended session refreshes that snapshot and exits; it does not resume questions.
   An active session's viewer may be restarted after an outage without changing
   answers or revisions. Confirm any continuation with the user; viewing alone
   is not resumption. Report explicit limitations if the host cannot run or stop
   a background process; do not silently fall back to a generic file server.

## 5. Verify completion and save the seed contract

Verify completion across the full ledger rather than the display alone: ensure all
active, parked, and undisplayed nodes are settled, cycles are resolved, and deferred
concerns are demonstrably non-blocking with documented reasons and revisit
conditions. Unresolved blockers halt completion.

Perform a local review of goal coverage, failure modes, security boundaries,
recovery, and verification. Also read the settled decisions against each other for contradictions (an ordering
rule that says "nothing first" beside an action marked "right away"), and check that the wording separates
what was **decided** from what was **done**: never write "exported" or "deleted" for something nobody did.
Every number in the seed contract comes from a command, not from a summary written by a model, including the
operator's. A factual claim about the machine or the repo may not settle a decision until you ran the check;
otherwise record it as an assumption. For each word a check depends on (safe, done, duplicate), name one case
that must fail it, and fix the definition if it would pass. Route newly identified blockers into the ledger and
return to Step 2 immediately. Then run the close checklist once:

- **What we haven't read:** name files or notes that are on disk but nobody opened
  this session — unsigned lessons, decisions never applied, tools never run,
  uncommitted changes, unread reviews. Each either gets read (return to Step 2)
  or lands in the seed contract as a named risk with who will read it.
- **Repeat surprises:** list only places where a surprise from this or an earlier
  session is cited. A cited surprise that contradicts a settled node's premise
  *is* new evidence: reopen it with `reopen_reason` per LEDGER §6.4. Surprises
  with no matching node stay risks only. No cited surprise, no entry.
  Findings feed seed contract Risks; they never reopen settled nodes without new
  evidence.

### Look for what we don't know we don't know

An unknown unknown cannot be listed, so do not pretend to. Do two things instead: **probe**, and
**say where you did not look**. Before presenting the seed contract, run at least three probes and
put at least one of them to the user (the others may be answered from evidence):

- **Pre-mortem:** "Imagine this shipped and turned out wrong. What is the most likely reason?"
- **Counter-example:** "Give me one case where this should not apply, or that would surprise you."
- **Outside view:** "What would someone who has done this before ask that we have not?"

- **Recoverability (for any decision that deletes, moves, or replaces something):** "What else holds a copy, and
  is that copy independent, or does it share the same disk or account?" Answer it with a check, not a guess.

Ask the probes the user must answer when the goal is confirmed (Session lifecycle step 4), **before** any message (a status update, a finding, or a frontier question) shows them anything you found; an answer given after seeing
your finding is not independent evidence, so record it as such (`NOT independent: asked after the finding`).

Record each as `Probe: <question> — answer: <the answer> — changed: <what it changed, or "nothing">`.
A probe that changed nothing is still recorded; record only a real change. Then write one line,
`Where we did not look:` — the repos, people, time span, or scenarios that were out of reach.
If the user skips a probe, record "skipped by the user". Fill this section with what was checked and what was missed.

Once the local review and close checklist are resolved:

1. Present the revision-labeled seed contract, opening with the **You are confirming** box, using the structure in [seed-contract.md](references/seed-contract.md) (on the lean path the file itself is the seed contract and uses the lean template), including
   actual accepted choices and their authority, with line 1
   `status: draft`. Line 1 becomes `status: confirmed for intake` only when the user affirms
   the displayed revision label, and only the helper in step 3 writes it. Describe the review as “I checked this draft for missing decisions and contradictions.”
   State its limits; this review does not verify implementation.
2. Ask for a **teach-back**: the user says in a sentence or two what will be built and what will not, and
   you list any mismatch with the seed contract (record "teach-back skipped" if they decline). Then ask the
   user to confirm that displayed revision. Confirmation requires the
   user to affirm the displayed revision label after the full seed contract is
   shown; "looks fine, start coding" before display is an incomplete stop.
   Confirmation applies strictly
   to the displayed content; any change to settled decisions, constraints, or
   cited evidence invalidates confirmation and requires renewed review. Ask for the
   confirmation by naming the three riskiest items — figures you invented, earlier
   decisions this reverses, placeholder names, or choices accepted without change —
   and say how many decisions were accepted as suggested versus chosen by the user.
3. Save every revision you display to `<session>/seed-contract.md`, beside `ledger.json`, with
   line 1 `status: draft`. The folder is the handoff: the seed and its ledger are saved together.
   Do not save a seed at the repository or workspace root. Overwrite only this session's own
   file. When the user affirms the displayed revision label, run
   ```sh
   python3 "<skill>/scripts/session.py" seed confirm "<session>" --revision "<the label>" --source "<the user's words>"
   ```
   The helper rewrites line 1 to `status: confirmed for intake`, adds a `Confirmed by:` line
   after the `revision:` line, and leaves every other line unchanged. It refuses, and writes
   nothing, when the seed is missing, line 1 is not `status: draft`, the label does not match the
   file's `revision:` line, the seed has no `## You are confirming` section with content after its `revision:` line, the source is empty, any ledger node is unresolved or flagged for
   review, the session is simulated or not active, or the seed is already confirmed. Never type
   the confirmed line by hand, and never run the helper before the user has affirmed that revision.
4. End the session as `completed`, save its final viewer snapshot, and stop the
   viewer process using **Session lifecycle**. Report the session folder, which holds
   `seed-contract.md` and `ledger.json`, as discovery input for downstream planning or
   implementation workflows, and stop. Leave commits to the user, and reserve
   downstream initialization, stage advancement, or implementation approval
   for subsequent workflows.

### Seed contract (artifact contract)

Read [seed-contract.md](references/seed-contract.md) before drafting the seed. Every displayed and saved revision follows it.

**Authorization:** Read-only investigation is a planning operation. Starting the
interview permits its local session ledger, snapshot, and loopback viewer lifecycle.
Confirmation authorizes writing the confirmed seed contract artifact alone;
implementation, source edits, migrations, or deployment require subsequent,
explicit user instruction after the artifact is saved. Treat earlier implementation
requests as superseded by the discovery phase. Any change to settled decisions,
constraints, or cited evidence invalidates that revision's confirmation and handoff.

**Complete when:** The confirmed revision is saved in the session folder and the folder's path reported. A
user-requested stop is a valid termination, but an incomplete seed contract is not completion.
