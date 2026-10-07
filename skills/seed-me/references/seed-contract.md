# Seed contract (artifact contract)

Read this before drafting the seed (SKILL.md Step 5.1). The displayed and saved revision must contain:

- Line 1, exactly one of three values and nothing else on that line: `status: draft` for every
  revision not yet confirmed, `status: confirmed for intake` only after the human affirms and the
  helper writes it, and `status: simulated` for an agent-mode session. The file is
  `<session>/seed-contract.md` in every case, saved beside `ledger.json`.
- Then the title and provenance: originator when known, a `revision:` line with the revision label and
  the date, and, once confirmed, the helper's `Confirmed by:` line, which says the seed is
  not approved for implementation.
- **You are confirming** box directly after the title and provenance lines, five short lines: the goal; what gets built;
  what does not; what the user accepted unchanged (with the accepted-versus-chosen count);
  what is still unknown — plus any earlier decision this reverses.
- Problem statement: current behavior, evidence, and why it matters.
- Proposed outcome: desired user-visible results and success criteria.
- Acceptance criteria: standalone testable checks, each opening with one plain-English line,
  then the exact command below it on a line starting `cmd:`, then `expect:` with the expected output, each independently
  verifiable without re-reading the interview. Every check that can run today copies a settled command as its exact command,
  with that command's settled expected output and where it runs — prose without those literals is
  not a criterion, and a substitute or extra command is not a check. This section is the executable core of the intake —
  downstream stages consume it verbatim.
  When the thing being specified does not exist yet, no settled command exists to copy. Write the check as a proposal:
  put `provisional:` before `cmd:` and name what must exist for it to run. Provisional checks record the intended
  behavior, do not block confirmation, and are never reported as verification; the implementation stage replaces
  each one with the real command once it can run.
- Affected users and systems: relevant repositories, modules, and execution paths.
- Constraints and boundaries: non-negotiables, exclusions, and rejected alternatives.
- Assumed defaults: every `assumed` entry, labelled as not confirmed by the user.
- Accepted decisions: actual answers, authority, rationale, and dependencies;
  distinguish user choices from evidence-derived facts and delegated choices.
- **Knowledge map**, in plain words, four parts:
  1. *What we know, with proof:* each item has its receipt and the date it was observed, and, for a fact that can
     change, a re-check trigger (`observed 2026-09-29; re-check if X changes or after N days`).
  2. *What we know we don't know:* each item with its owner and how to find out.
  3. *What we have not read:* the close checklist's unread material.
  4. *What could surprise us:* the `Probe:` lines, `Where we did not look:`, and what would tell us we were
     wrong (a concrete signal, not a mood).
- Evidence and uncertainty: inspected paths, measurements, unverified hypotheses,
  assumptions, what we haven't read (from the close checklist), and repeat
  surprises with their citations. Carry a `Grounded in:` list of paths actually read
  this session. Flag a stale watch: any cited source older than the session start
  or since modified is suspect until re-read. Record verified origins and state
  gaps explicitly rather than inventing missing provenance.
- Suggested first slice: the smallest implementation step that would start
  resolving the problem, labeled proposal only, stated as an exact first
  command with its working directory. Non-binding: it seeds Stage 01
  approach drafting without preempting design or authorizing work.
- Risks and verification: consequential failure modes, mitigations, and testable
  acceptance criteria; distinguish proposed checks from completed verification.
- Open questions and deferrals: only non-blocking items, with reasons and revisit
  conditions. Unresolved blockers still prevent confirmation and saving.
- Owners and next steps: for each open blocker, the owning decider and gate; for each
  item to be read later, who will read it; for each repeat surprise, its guardrail.
  Map each to ledger status: known → settled (evidence), needs a decision →
  unresolved (blocker), watch → parked or risk, repeat surprise → risk with guardrail.
- Downstream handoff: the session folder is the handoff: `<session>/seed-contract.md` together with
  `ledger.json`, which a consumer needs to see that the session completed with a human. The viewer
  page is not required. This artifact
  is discovery input, not an implementation plan,
  approved specification, or review receipt. Preserve accepted constraints when
  deriving downstream plans or specifications; follow the selected workflow's
  active contract and surface conflicts rather than silently replacing decisions.
  Do not preselect a downstream profile or fabricate stage approval.

Label technical proposals as proposals unless explicitly accepted; downstream
workflows own subsequent specification and implementation approval.
