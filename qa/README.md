# seed-me QA: deterministic conduct checks

`seed_me_conduct.py` checks seed-me's own rules with code only (regex, counting, the session validator). No network, no writes, standard library only. Fuzzy judgments belong to a later layer.

```sh
# interviewer turns in a Claude Code transcript (list simulated-operator agent ids to enable the leak rule)
python3 qa/seed_me_conduct.py turns ~/.claude/projects/<project>/<session>.jsonl --operators <id>,<id> --since 2026-09-29 --show-fails
# saved seed-me sessions (validator + authority hygiene)
python3 qa/seed_me_conduct.py ledgers [sessions-dir]
# seed contract files (check-line format, confirming box, simulated labelling)
python3 qa/seed_me_conduct.py contracts path/to/seed-contract*.md
```

Add `--strict` to exit 1 when any check fails.

## Limits (know these before trusting a number)
- **Epochs:** a rule only applies to turns written after the rule existed. Use `--since` with the commit date of the rule; older turns fail by construction.
- **Question-turn detection is structural:** it looks for the template's own line starts (`Option A`, `My suggestion`, `What's your instinct?`). A design question asked in the same format outside a real run still gets the ledger-footer rule (a known false positive).
- **Length limit (450 words) is the checker's own number,** an informational flag, not a finding about quality.
- **It cannot judge meaning:** whether Option B is a strawman, whether the evidence is relevant, whether a guess was verified. That is the Jev layer in `docs/seed-me-qa-plan.md`.
