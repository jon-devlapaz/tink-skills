# Epistemic lenses — per-turn routing menu for `seed-me`

Each ready question may draw on one lens per turn, selected by a Jev Choice
call (see SKILL.md Step 3). Lenses are advisory reading aids, never authorities:
evidence, owners, and ledger rules govern. If the call is skipped or fails, the
host proceeds without a lens and logs the skip.

| Lens key | Source | Use when the turn needs |
|---|---|---|
| `quadrant-audit` | epistemic-matrix, Workflow §2 | sorting what is known / unknown / unknowingly known before asking |
| `receipt-check` | epistemic-matrix, Doctrine §1 | verifying a Q1 claim actually has on-disk evidence |
| `owner-gate` | epistemic-matrix, Q2 table | naming the decider and the answer shape that settles the ask |
| `breeding-scan` | epistemic-matrix, Doctrine §2 | checking whether the concern is a ground where past surprises bred |
| `ledger-persist` | decision-ledger (epistemic-skills) | deciding how the eventual answer will be recorded durably |
| `none` | — | the turn is answerable from cited lines alone; no lens needed |

Selection state per turn: goal, the ready node's evidence summaries, and the
owner named so far. Verdicts apply only at confidence ≥ 0.50 with option lead
≥ 0.10; anything else falls back to `none` with the gate outcome logged
(`applied|gated-out(conf,lead)|skipped(reason)`). A lens never overrides
evidence, owners, prohibitions, or settled answers, and never produces
recommendation prose — the host writes that from cited lines.

## Session setup (once, before the first lens call)

1. **Opt-in.** Lens calls are off by default. Ask the operator once per
   session whether to use them; ordinary interviews need no key. A "no"
   ends this section — the interview runs fully without lenses.
2. **Authorization.** Confirm the existing session authority covers
   transmitting evidence summaries to the model provider. Never send secrets,
   credentials, or private material; when in doubt, redact the concern to its
   shape ("auth flow, 2 concerns") rather than its contents.
3. **Preflight.** The menu above is frozen for the session: record its hash
   and the pinned model before the first call. If the menu changes mid-session,
   re-preflight; verdicts from a stale menu are discarded.

Failed, timed-out, or low-confidence calls resolve to `none` (unresolved),
never to a forced lens. The transcript is the receipt: menu hash, per-turn
verdict or skip reason, gate outcomes.
