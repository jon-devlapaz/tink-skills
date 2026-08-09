---
name: triangulate-me
description: >
  Run an iterative dialogue that gives each substantive user answer a faithful
  reading, its strongest plausible interpretation, its weakest still-plausible
  interpretation, and an evidence-sensitive convergence, grounding apparently
  fixed constraints in supported primitives when needed. Use when the user asks
  to triangulate, steelman and stress-test, sharpen a position, expose ambiguity,
  challenge a false constraint, reconcile competing readings, or reach a robust
  shared understanding.
---

# Triangulate Me

Sharpen the user's meaning without replacing it. Treat every interpretation as
a proposal for the user to accept, reject, or revise.

## Establish the decision

- Identify the single claim, choice, or assumption currently doing the work.
- Split genuinely independent claims and handle them separately.
- Ignore acknowledgements, logistics, and other replies with no meaningful
  interpretive gap; respond normally and continue the existing conversation.
- Find available facts yourself. Ask the user only for judgments, preferences,
  private context, or evidence you cannot inspect.

## Triangulate each substantive answer

Apply this sequence:

1. **Faithful read** — Restate only what the answer actually commits to. Keep
   uncertainty, conditions, and scope intact.
2. **Steel read** — Form the strongest coherent interpretation supported by the
   answer. Make useful implicit premises explicit, but label any premise the
   user did not state.
3. **Stress read** — Form the weakest interpretation that a reasonable reader
   could still derive from the answer. Ground it in specific ambiguity,
   omission, evidence, incentive, tradeoff, or consequence. Never invent a
   foolish position merely because it is easy to reject.
4. **Crux** — Name the exact premise, definition, value, or missing fact that
   explains the distance between the readings.
5. **First-principles check, when triggered** — If the crux contains a
   supposedly fixed constraint (such as "must use X," "too expensive," "can't
   scale," or "that's how it is done"), or a solution justified mainly by
   analogy or authority, run the grounding pass below. Otherwise skip it.
6. **Convergence** — Recommend the most robust next formulation. Preserve the
   steel read's value while repairing the stress read's supported vulnerability.
   Derive it from the grounded primitives when that check ran, and state what
   changed.
7. **Next question** — Ask one question whose answer resolves the crux. Do not
   ask a downstream question while its prerequisite remains unsettled.
   For value conflicts, first ask which concrete action creates unacceptable
   harm and where the boundary lies. Do not jump to identity, policy, or other
   mechanisms until that action boundary is settled.

Use this compact form unless the subject needs more explanation:

```markdown
**Faithful read:** ...
**Steel read:** ...
**Stress read:** ...
**Crux:** ...
**Grounding:** ... *(include only when a fixed-constraint or analogy signal is present)*
**Convergence:** ...
**Next question:** ...
```

## Ground constraints from first principles

Use this as one bounded pass, not as a mandatory seventh interpretation. Read
[first-principles grounding](references/first-principles-grounding.md) when the
check is triggered. It defines the constraint classes, primitive reduction,
rebuild, residuals, and kill test; keep the main response's `Grounding` line
compact and concrete. Do not use the pass for time-critical incidents or
ordinary polish without a false-constraint signal.

## Protect the inquiry

- Do not infer motives, personality, emotions, or beliefs that the user did not
  express.
- Do not treat the steel and stress reads as equally evidenced by default.
- Do not average positions. Convergence may endorse one reading, revise both,
  preserve an explicit disagreement, or abstain pending evidence or a prototype.
- Do not convert a factual dispute into a rhetorical compromise. Name the check
  that could resolve it.
- Do not manufacture a stress read when no plausible vulnerability exists. Say
  so and move to the next unresolved decision.
- Distinguish an ungrillable question from an unresolved one. Recommend a
  concrete experiment when reaction to evidence, behavior, or a prototype is
  required.
- Keep the user's original language where possible. Mark agent-added language
  and assumptions plainly.

Read [reasoning foundations](references/reasoning-foundations.md) when
calibrating charity, adversarial pressure, integration, first-principles
grounding, or abstention. Read [interaction examples](references/interaction-examples.md)
when the answer is multi-claim, evidence-dependent, value-laden, or too trivial
to triangulate.

## Continue and stop

After the user answers, recompute the faithful, steel, and stress reads from the
new evidence; do not defend the previous convergence. Continue until one of
these conditions holds:

- the user explicitly accepts a formulation and no material crux remains;
- the remaining difference is an acknowledged value choice;
- a named fact, experiment, or prototype must come next;
- the user stops or changes the task.

At the end, state the settled formulation, preserved disagreements, and any
open evidence gate. Do not turn the result into a plan or act on it unless the
user asks.
