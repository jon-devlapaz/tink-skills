# Lean path

For a small, easily reversed idea, keep one markdown file, `seed-contract.md`, that the user
and the agent both edit. Once the goal is confirmed, start the session and viewer using
**Session lifecycle** in SKILL.md, exactly as on Full. Keep the interview short: the viewer
does not add questions, dependencies, or implementation permission. Scripts validate the
ledger; the agent remains responsible for the meaning of the Markdown and its agreement with the ledger.

## When to use it (the size gate)

Lean only if **all** of these hold; otherwise take the full path:
- one component or one area of the code;
- every consequential choice is cheap to undo;
- one user, one machine;
- no security, data loss, public exposure, or financial action (moving money, charging, or
  changing financial records); a local helper that only drafts or reads is fine;
- about three or fewer questions would change what gets built.

The agent proposes a path in one line with its reason. The user can say "lean" or "full" at
any time. Switching to full continues the same session without discarding this file's items.

## Rules

0. When you create the file, print its absolute path as a `file://` link in the same message.
   Start and link the viewer immediately after confirmed-goal publication, without a separate request.
   End every question turn with `Ledger: <viewer URL>` (or the saved HTML snapshot link when
   the server cannot run, with the actual reason). Follow **Session lifecycle** for startup, status,
   snapshot, completion, and stopping only the owned viewer process.

1. Every item has an id (`G`, `D1`, `C1`, `A1`, `Q1`, `E1`) and an author tag: `[user]`, `[agent]`,
   `[evidence]`.
2. A decision is `[user]` only if it quotes the user's words or cites the chat turn. Facts the agent
   found are `[evidence]` with a `file:line` quote. Everything else the agent writes is `[agent]`, a proposal.
3. Proposed changes to existing text go in a blockquote under the item, never in its body:
   `> agent proposes (YYYY-MM-DD): <new wording> — why: <reason>`. The user accepts by moving the
   wording into the item and deleting the blockquote.
4. Human edits are never overwritten. The agent responds to edits only when asked in chat.
5. One question at a time. A real choice gets the full question format (two options, undo cost,
   the case against the suggestion, and instinct first when an option is hard to undo). A plain
   factual question (where something lives, what a name is) is just asked, in one sentence.
6. When later evidence contradicts a decision, edit the decision and note why in the item; do not
   leave both standing.
7. Before confirming, ask the open probes before showing any finding, and for any deletion ask the recoverability probe. Run three probes (a pre-mortem, a counter-example, an outside view), put at least one to the
   user, and fill the Knowledge map honestly; ask for a one-sentence teach-back.
8. Accepting wording is not approval to implement. Confirmation is the user setting `status: confirmed`.

## Keep the ledger and editable file in agreement

Use the existing `session.py read` and `publish` commands in **Session lifecycle**. There is
no automatic Markdown import and no new helper is required. After each actual answer or inspected fact,
publish its corresponding node and update only agent-owned Markdown. Reread the file before
editing or publishing so human edits are never overwritten. If a human edit conflicts with the
ledger, preserve the edit and ask about the conflict in chat; do not silently treat it as a new
accepted answer. Keep proposals as proposals, not settled nodes. Assumptions belong in `assumed`.
Do not add prerequisites just to make the graph appear: independent concerns use `[]`.

For each publication, read the latest ledger and write `<session>/update.json` with
`expected_version` from that read, an actual `reason`, and `state` containing only `status`,
`draft`, `goal`, `origin`, `current_question`, `nodes`, and optional `assumed`/`operator`.
Strip helper-owned node `history` and `revision`. For the first publication, set `goal` to the
confirmed text and `origin` to the goal item's id; include a settled `decision` node with that
same answer, `prerequisites: []`, `evidence: []`, `owner`, `gate`, `authority: user`, and the
actual confirmation turn as `authority_source`. Simulation uses `simulated`, never `user`.
Each later concern has stable `id`, `kind` (`decision` or `fact`), `status`, `prerequisites`,
and `evidence`; decisions need `owner` and `gate`. Settled items also need `answer`,
`authority` (`user`/`delegated` for decisions, `evidence` for facts), and `authority_source`;
evidence-derived or delegated settlement needs inspected `evidence`. Unresolved items carry
no answer or authority. `current_question` is one ready decision id, or `null`.
A non-blocking deferral needs `defer_reason` and `revisit_condition`; an unresolved blocker
still prevents completion. Reopening clears answer/authority/source and adds `reopen_reason`.
The helper validates the state and retains history; report rejected or stale publications.

The Markdown contract revision and confirmation are separate from the ledger's helper-owned
premise revision and publication version. Publishing or opening the viewer does not confirm
the contract. End as `completed` only after actual contract confirmation and a successful save;
stop preserves unanswered questions. `seed-contract.md` is the sole downstream handoff;
the ledger and viewer are interview records, not extra required downstream artifacts.

## Template

```markdown
# Seed contract: <title>
status: draft | confirmed        revision: 1        date: YYYY-MM-DD

## You are confirming
- Goal: ...
- What gets built: ...
- What does not: ...
- Accepted unchanged: N of M suggestions (chosen by you: K)
- Still unknown: ...

## Now  (the agent keeps these current)
- Settled: ...   - Uncertain: ...   - Needs you next: ...

## Goal
G [user] <one sentence>

## Decisions
D1 [user|delegated|evidence] <decision> — source: <the user's words, chat turn, or file:line>

## Assumed (not confirmed by you)
S1 [agent] <default> — why it is safe: ...

## Constraints and exclusions
C1 [user] ...

## Acceptance checks
A1 [user|agent] <plain-English line>
   cmd: `<exact command>` | expect: <expected output> | cwd: <path>
   (Not built yet? Write `provisional:` before `cmd:` and say what must exist for it to run. It records the intent,
   does not block confirmation, and is never reported as verification.)

## Open questions
Q1 NEXT [agent] <title> — owner: <who decides> — why it matters: ...

## Knowledge map
- **What we know, with proof:** E1, E2 ... each with the date observed and, if it can change, `re-check if ...`.
- **What we know we don't know:** each item with an owner and how to find out.
- **What we have not read:** ...
- **What could surprise us:**
  Probe: <question> — answer: <answer> — changed: <what it changed, or "nothing">
  Probe: ...
  Probe: ...
  Where we did not look: <repos, people, time span, scenarios>
  We would know we were wrong if: <a concrete signal>

## Evidence
E1 [evidence] "<quoted line>" (<path>:<line>) — observed YYYY-MM-DD; re-check if <trigger>
```

The file must still open with **You are confirming** and carry executable acceptance checks: the
lean path drops the extended interview structure, not the viewer or the honesty.
