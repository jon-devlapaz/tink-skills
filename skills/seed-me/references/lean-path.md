# Lean path

For a small, easily reversed idea, skip the session, ledger, and viewer. Keep one markdown
file, `seed-contract.md`, that the user and the agent both edit. The rules are typed but soft:
nothing is enforced by scripts, so the agent holds itself to them and says so when it cannot.

## When to use it (the size gate)

Lean only if **all** of these hold; otherwise take the full path:
- one component or one area of the code;
- every consequential choice is cheap to undo;
- one user, one machine;
- no security, data loss, public exposure, or financial action (moving money, charging, or
  changing financial records); a local helper that only drafts or reads is fine;
- about three or fewer questions would change what gets built.

The agent proposes a path in one line with its reason. The user can say "lean" or "full" at
any time. Switching to full publishes this file's items as the first ledger update.

## Rules

0. When you create the file, print its absolute path as a `file://` link in the same message, and end
   every question turn with `Ledger: <that link>`.

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
- **True but nobody has read:** ...
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
lean path drops the machinery, not the honesty.
