---
name: triangulate-me
description: Triangulate a claim through faithful, steel, and stress reads, then isolate the crux and converge without false compromise. Use when pressure-testing an interpretation, exposing the crux between plausible readings, grounding a supposedly fixed constraint, or converging without false compromise.
---

# Triangulate Me

Sharpen the user's meaning without replacing it. Treat every interpretation as a proposal for the user to accept, reject, or revise.

**Invariant:**
- Ground every interpretation in the user's expressed language and context; exclude unstated motives, emotions, or psychological speculation.
- Weight reads by evidence; empirical measurements and concrete harm barriers strictly outweigh aesthetic preference, precedent, or unverified assertion.
- Avoid false compromise; endorse well-supported positions directly, revise both sides, or preserve genuine value conflicts without manufacturing midpoint compromises or artificial objections.
- Confine actions to analysis and diagnostics; wait for explicit user approval before planning, code modification, or execution.

## 1. Triage and isolate the claim

- **Fast-path**: If the input is an acknowledgement, logistics, or has no substantive interpretive gap, respond directly and stop without running the frame.
- Isolate the single active claim, choice, or assumption doing the work. Split independent claims and handle them separately.
- Inspect accessible facts autonomously; ask the user only for uninspectable context, judgments, or private preferences.

**Complete when:** Exactly one active claim, choice, or assumption is isolated, or a direct fast-path response is emitted.

## 2. Differentiate interpretations

1. **Faithful read** — Restate only what the answer explicitly commits to, keeping every meaning-changing qualifier intact.
2. **Steel read** — Construct the strongest coherent interpretation supported by context; make any agent-added premise explicit and labeled.
3. **Stress read** — Name the weakest plausible vulnerability supported by the answer, or state that none exists.

*Load [references/reasoning-foundations.md](references/reasoning-foundations.md) to calibrate charity, adversarial plausibility, and differentiation.*

**Complete when:** All three reads are bounded by stated evidence and agent premises are explicitly labeled.

## 3. Isolate the crux and ground constraints

- **Crux** — State declaratively the exact premise, definition, value conflict, or missing evidence explaining the divergence between reads. Avoid phrasing the crux as a question.
- **First-principles check (when triggered)** — If the crux involves a supposedly fixed constraint (such as "must use X," "too expensive," "cannot scale," or "industry standard") or a solution justified by analogy or authority, load [references/first-principles-grounding.md](references/first-principles-grounding.md). Classify constraints, reduce to supported primitives, discard unsupported assumptions, and state the cheapest kill test. Otherwise, skip grounding.

**Complete when:** The crux is declaratively stated, and any fixed-constraint signal is grounded to primitives.

## 4. Formulate convergence

Recommend the most robust formulation: preserve the steel read's value while repairing the stress read's supported vulnerability.

- **Direct endorsement**: If one position is already bounded, testable, and well-supported, endorse it directly without manufacturing counter-objections or exceptions.
- **Value conflicts**: Anchor the conflict in concrete actions and harm boundaries before procedural mechanisms; preserve distinct values without forcing an arbitrary compromise.
- **Missing evidence / empirical gates**: Defer conclusions and name the specific diagnostic check, trace, or bounded experiment (with predeclared decision rules and harm guardrails) required to decide.

**Complete when:** The formulation explicitly states what is preserved, repaired, or left unresolved.

## 5. Sequence the next gate or stop

- Ask at most one question addressing the immediate prerequisite crux; ask zero questions if convergence settles the decision or an evidence gate is named. Never repeat the crux as a question.
- Stop when the formulation is accepted, value choice is acknowledged, or an evidence gate is reached. Wait for explicit user instruction before planning or executing downstream work.

*Load [references/interaction-examples.md](references/interaction-examples.md) for calibration on multi-claim, value-laden, evidence-gated, or trivial cases.*

### Output Schema

Lead with the decision or direct answer. When a substantive interpretive gap warrants inspection, use this compact form:

```markdown
**Faithful read:** ...
**Steel read:** ...
**Stress read:** ...
**Crux:** ...
**Grounding:** ... *(include only when a fixed-constraint or analogy check ran)*
**Convergence:** ...
**Next question:** ... *(omit when zero questions remain)*
```

**Complete when:** The output is emitted with at most one prerequisite question, and all downstream action remains gated.
