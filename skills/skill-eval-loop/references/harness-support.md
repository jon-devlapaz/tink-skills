# Harness evidence matrix

Last reviewed: 2026-08-12 (America/Chicago).

The evaluator implements adapters for four harnesses. “Implemented” means the
repository constructs isolated invocations, parses traces, and exercises a
complete fake run in the deterministic test suite. It does not mean a real
installed CLI has passed on the immutable release candidate.

| Harness | Deterministic repository evidence | Latest real-CLI evidence | Release status |
| --- | --- | --- | --- |
| Pi | `RuntimeTests`, `EndToEndTests.test_fake_runs_complete_for_every_selected_harness` | 2026-08-13 UTC: valid five-case bounded diagnostic against the current `triangulate-me` payload; local ignored `.eval-runs/triangulate-me/run-20260813T-candidate-v1-five-risk-cases/` only | Implemented; release verification pending |
| Codex | `RuntimeTests` cover isolated home, persisted rollout, model identity, and forced-skill access; fake end-to-end run | Not established for the current candidate | Implemented; release verification pending |
| Claude Code | Invocation isolation and fake end-to-end run | Not established for the current candidate | Implemented; release verification pending |
| Hermes Agent | Disabled-tool configuration, trace parsing, Herdr transport, and fake end-to-end run | Not established for the current candidate | Implemented; release verification pending |

The Pi diagnostic proves only that one configured Pi/model/task combination
completed with valid artifacts. It is not a portability result, does not prove
the other adapters, and is not retained in the published package.

## Release-verification gate

Promote a harness from “implemented” to “release verified” only after a clean
smoke using that harness's real executable against the exact immutable candidate:

1. record executable version, exact provider/model id, candidate commit, and
   skill payload digest;
2. run one audited paired case with the minimum required tools;
3. require `artifact_valid`, `mechanism_valid`, and runtime attestation to pass;
4. retain the manifest, benchmark, raw trace, grading, and redacted setup
   evidence outside the published skill payload;
5. record the UTC completion date and evidence location in this matrix.

A failed, blocked, stale, or predecessor-candidate smoke remains visible as
such; it must not be summarized as current support.
