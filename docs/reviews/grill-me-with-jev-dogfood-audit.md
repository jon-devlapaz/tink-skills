# Jev dogfooding audit and next experiment

Date: 2026-09-22. Evaluation only. No operational skill, installed skill, or production behavior changed. No paid calls made in this audit.

## Verdict

| Use | Verdict now | Basis |
| --- | --- | --- |
| Ask / investigate / continue Choice | Insufficient evidence; avoid expansion | Three easy synthetic tasks reached the same decisions with and without advice. The host had already been instructed to reason through each concern. |
| Question-economy screening | Test first; no deployment yet | A real replay defect was a redundant/entailed question, and a focused host-only instruction fix corrected one case. Incremental Jev value is unmeasured. |
| Change-impact screening | Insufficient evidence | No controlled Jev comparison exists; ledger bookkeeping tests do not measure semantic dependency detection. |
| Candidate risk screening (Noul) | Insufficient evidence | Existing Noul cases used supplied candidates only. No evidence of better candidate generation or overall risk coverage. |
| Broad option selection and probability badges | Redesign or omit pending evidence | Choice returns a selected option and distribution, not an explanatory rationale. Current 0.10 lead, 0.50 confidence, and Noul >0.80 rules have no domain calibration. |

**Smallest justified next change:** none to the operational skill. Run a narrow, harder question-economy comparison against a host-only check with identical wording and candidate sets. Keep the existing evidence-first and authority safeguards in every arm.

## Evidence inventory and methodology audit

- Source skill: `skills/grill-me-with-jev/SKILL.md` version 1.2.1, SHA-256 `6d047f6ec3dc251f55adf6d89b9e5a2c3d8657d53b9cdd2dc863e93cb87f9632`, repository HEAD `35fce56c11d42580dffec2b3718632f35ce72610`. Installed `.agents/skills/grill-me-with-jev/SKILL.md` is version 1.1.0, SHA-256 `b316895e6e6140fc22997b3e47b8b579cdf85f7123da302ec8b5b14501f19f40`; do not conflate them.
- Prior harness: `run_experiments.py`, `codex-cli 0.154.0`, no host model override; exact served host model ID is unavailable. Prior successful TypeSafe receipts are reported as `jev-1.13.0`. Provider advice was prefetched and replayed into a separate host process. Original arm order was fixed, one run per case, concurrent workers two. Three synthetic cases each had two required questions and one supplied review candidate. This has a ceiling and cannot measure risk discovery or real user satisfaction.
- Prior report: all 12 episodes had two required decisions in one interruption and zero measured omissions/unnecessary questions. This supports only “no observed gain on these cases.” It does not establish H1 generally. Provider time was outside replayed host wall time. Three initial HTTP 529 failures were kept as fallback evidence, and the pre-settlement review packet error was corrected in the published summary.
- The raw `evals/results/` directory referenced by the prior review is absent from this checkout. Thus the receipts, complete transcripts, request hashes, and per-run counters cannot be independently re-adjudicated here. Do not treat the review prose as raw data.
- Current TypeSafe docs: `POST /v1/systemone` accepts `state`, `model`, and named typed `questions`. Choice returns `choice`, all option probabilities, and distribution-derived `confidence`; Noul returns a yes probability without separate confidence. Question IDs are not model input. The pinned Jev 1.13 model is text-only, has 64k total and 32k state-plus-longest-question token limits, a published $0.042 per million input tokens and free output tokens, and currently listed 250k tokens/s and 1,200 requests/minute limits. Limits can change. Output type does not establish judgment correctness. [API](https://docs.typesafe.ai/api), [models and pricing](https://docs.typesafe.ai/models), [Choice](https://docs.typesafe.ai/primitives/choice), [Noul](https://docs.typesafe.ai/primitives/noul), [confidence](https://docs.typesafe.ai/confidence).

## Hypotheses and disconfirmation targets

| Hypothesis | Existing case/result | Disconfirming observation to seek | Main limitation |
| --- | --- | --- | --- |
| H1 routing redundant | Prior webhook/migration/alerts: same measured outcomes in four arms | Jev corrects a host routing miss on held-out hard states without causing an equally costly new miss | Easy fixed candidates; no live end-to-end timing |
| H2 narrow economy valuable | Retention turn 12 repeated an arguably entailed replay question; host-only 1.2.1 retest suppressed a narrower version | Host-only targeted check matches or beats Jev; Jev suppresses the consequential manual-replay question | One host-only focused retest; no Jev comparison |
| H3 change impact valuable | Ledger prototype tests graph traversal only | Jev detects a missing semantic edge while preserving independent accepted answers more often than host-only | No behavioral runs |
| H4 risk screening valuable | Two material and one handled supplied review candidates were classified correctly in every prior arm | Host-only generates/handles risks equally well, or Jev misses supplied risks and adds reopenings | Candidate discovery untested |
| H5 poor fit | Current broad option query asks for a stated tradeoff; Choice wire response cannot return prose. Thresholds are unvalidated | Narrow Choice improves grounded option recommendation and badges improve observed user decisions | No user study or calibration corpus |

## Pilot artifacts and rules

`skills/grill-me-with-jev/evals/dogfood-pilot.json` contains five development and eleven held-out synthetic states, with reference judgments written before any new outputs. They include the apparently redundant but consequential manual replay question, a genuinely entailed question, inspectable and inaccessible facts, a conditional answer, changed premises, an unrecorded semantic dependency, an independent decision, a handled concern, a missing risk, conflict and stop, repository instruction text, and insufficient architecture evidence. Multiple defensible answers can be listed. These are synthetic, not consented real planning interviews.

`skills/grill-me-with-jev/evals/dogfood_pilot.py prepare --out <directory>` writes a manifest and actual TypeSafe request shapes offline. `run` is explicitly gated by an approved budget flag and is limited to three development cases and nine matched-state jobs. It uses the source skill for the current-routing arm, a host-only baseline, and a targeted Jev arm. Order is seeded and shuffled. It records the prompt hash, provider request and response, host output, token usage when exposed, errors, and separate host/provider wall time. The host model remains unpinned and should be obtained from run metadata if the CLI exposes it; otherwise report it unknown. The flag is not itself authorization: obtain explicit approval for both host and Jev spending first. No live run has been made.

Before any held-out run, freeze prompts, adjudication rubric, and stopping rule. Use blinded human adjudicators where possible, allowing “ambiguous” and multiple defensible choices. A scripted user must disclose only requested answers and keep them identical across arms. End-to-end simulations must run the actual call on the critical path and measure interruptions, candidate generation, downstream rework, retries, cache, total wall time, and spending. The current pilot does **not** do that. Include a host-only version of every targeted check. Randomize arm order, repeat within the approved cap, and retain failed/fallback runs separately. Test wording, irrelevant context, and batch composition on a bounded development subset; do not tune thresholds on held-out cases.

Predeclared decision rule for later evaluation: a missed consequential decision or authority/stop violation outweighs at least five extra questions and is reported individually, never hidden in a mean. Promote a targeted Jev check only if it reduces consequential misses or unnecessary interruptions on held-out cases beyond the matched host-only check, with no authority/stop regressions, and its full end-to-end cost is acceptable to the user. Otherwise keep local handling. With small samples, report counts and uncertainty rather than a significance claim. Treat badges as uncalibrated until held-out calibration and user effects are measured.

## Transcript availability

The prior report gives aggregate outcomes, not accessible per-case transcripts. It would be misleading to present fabricated side-by-side exchanges. For a measured unchanged outcome, the reported webhook case had two decisions resolved in one user interruption in local, Choice, Noul, and combined arms; all classified the supplied lease concern as material. The new pilot receipt file is designed to preserve exact side-by-side prompts and responses for wins, failures, and unchanged outcomes after authorized execution.

## Largest uncertainty

Whether a narrow Jev economy check catches consequential question errors that an equally explicit host-only check misses. Resolve this with the prepared matched-state pilot, then a small, consented and sanitized real-plan interview set. A Jev win on hard held-out cases with no consequential suppression would change the recommendation toward a narrow integration. Host parity or Jev suppression of a real consequential choice would argue against adding it.
