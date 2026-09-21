# Experiment plan: simpler execution without weaker decisions

Source: user feedback after the [hardening review](../reviews/grill-me-with-jev-review.md).
Scope: measurement infrastructure plus narrow trigger and question-selection edits.
The previous prohibition on a new runtime state service remains in effect; the
ledger prototype is isolated under evals and is not used by the installed skill.

## Questions, in user priority order

1. Does a broader description recognize adversarial planning requests while
   excluding normal reviews, summaries, execution, load tests, and no-interview asks?
2. Does Choice, Noul, or their combination improve decisions relative to local
   evidence-first routing, and what actual token/latency overhead does it add?
3. Are earlier constraints, actual answers, dependencies, and confirmation state
   retained after intervening turns and material changes?
4. Can a tiny deterministic ledger reliably handle bookkeeping without deciding
   materiality, intent, predicate truth, or which descendant answers remain valid?
5. Can each question be justified by meaningfully different implementation, risk,
   cost, reversibility, or behavior, and can independent decisions share a round?

## Comparison design

- Activation: description-only prompts with near-neighbor negatives; preserve the
  old-description baseline. Do not supply expected labels to the evaluator.
- Ablation: identical core/reference and fixed synthetic candidate coverage;
  four arms isolate Choice and Noul. A deterministic oracle supplies user answers
  and synthetic inspection results only when requested. A separate settled-state
  snapshot evaluates the named completion concern. Advice is real TypeSafe output,
  prefetched once and replayed, with failures explicitly recorded.
- Retention: replay 16 user turns sequentially with full history and prior ledger;
  include a conditional cost, parent change, repeated answer, narrow delegation,
  unrelated background, and confirmation followed by material change and stop.
- Ledger: software tests assert atomic cycle rejection, transitive dirty marking,
  unresolved-node accounting, actual-answer preservation, and stale confirmation
  rejection. This does not establish benefit of integrating it with an LLM.

## Decisions this pilot may support

A reproducible failure warrants a narrow fix. An equal score on this small corpus
supports “no measured benefit here,” not removing Jev everywhere. No runtime
ledger integration without a controlled state-retention comparison that includes
its added protocol/tool cost. No extra product capabilities or authority changes.

Record actual host/provider token counts and latency, required choice omissions,
unnecessary questions, simulated interruptions/corrections, retained decisions,
repeat questions, and premature acceptances. Distinguish settled-choice rounds from
turns to a real saved plan. Missing metrics are unknown, not zero.

## Evidence and limitations

Results are in [experiment review](../reviews/grill-me-with-jev-experiments.md), with
raw JSON under `skills/grill-me-with-jev/evals/results/`. The first ablation pilot
had inaccessible synthetic file evidence; preserve it separately and rerun after
adding identical oracle inspection facts to all arms. Do not silently revise its
outcomes. Provider overload and host usage failures stay visible in the report.

This local pilot is not randomized, multi-seed, compaction, weaker-model, or real-user
validation. Those limits prevent a production-value claim; they do not prevent
shipping the narrow trigger clarification and minimum-sufficient-question rule.
