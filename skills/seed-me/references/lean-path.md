# Lean path

For a small, easily reversed idea, skip the session, ledger, and viewer. Keep one markdown
file, `seed-contract.md`, that the user and the agent both edit. The rules are typed but soft:
nothing is enforced by scripts, so the agent holds itself to them and says so when it cannot.

## When to use it (the size gate)

Lean only if **all** of these hold; otherwise take the full path:
- one component or one area of the code;
- every consequential choice is cheap to undo;
- one user, one machine;
- no security, data loss, money, or public exposure;
- about three or fewer questions would change what gets built.

The agent proposes a path in one line with its reason. The user can say "lean" or "full" at
any time. Switching to full publishes this file's items as the first ledger update.

## Rules

1. Every item has an id (`G`, `D1`, `C1`, `A1`, `Q1`, `E1`) and an author tag: `[user]`, `[agent]`,
   `[evidence]`.
2. A decision is `[user]` only if it quotes the user's words or cites the chat turn. Facts the agent
   found are `[evidence]` with a `file:line` quote. Everything else the agent writes is `[agent]`, a proposal.
3. Proposed changes to existing text go in a blockquote under the item, never in its body:
   `> agent proposes (YYYY-MM-DD): <new wording> — why: <reason>`. The user accepts by moving the
   wording into the item and deleting the blockquote.
4. Human edits are never overwritten. The agent responds to edits only when asked in chat.
5. One question at a time, with the same question format as the full path (two options, undo cost,
   the case against the suggestion, and instinct first when an option is hard to undo).
6. When later evidence contradicts a decision, edit the decision and note why in the item; do not
   leave both standing.
7. Accepting wording is not approval to implement. Confirmation is the user setting `status: confirmed`.

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

## Open questions
Q1 NEXT [agent] <title> — owner: <who decides> — why it matters: ...

## Evidence
E1 [evidence] "<quoted line>" (<path>:<line>)
```

The file must still open with **You are confirming** and carry executable acceptance checks: the
lean path drops the machinery, not the honesty.
