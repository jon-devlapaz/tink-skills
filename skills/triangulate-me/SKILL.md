---
name: triangulate-me
description: >
  Triangulate a claim through faithful, steel, and stress reads, then identify
  its crux and evidence-sensitive convergence. Use when the user asks to
  pressure-test an interpretation, expose the crux between plausible readings,
  ground a supposedly fixed constraint, or converge without false compromise.
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

**Complete when:** exactly one active claim, choice, or assumption is named. If
the reply is not substantive, respond normally without running the frame.

## Triangulate each substantive answer

Apply this sequence:

1. **Faithful read** — Restate only what the answer actually commits to.
   Complete when every qualifier that changes the meaning remains intact.
2. **Steel read** — Form the strongest coherent interpretation supported by the
   answer. Complete when every useful agent-added premise is explicit and
   labeled.
3. **Stress read** — Form the weakest interpretation that a reasonable reader
   could still derive from the answer. Complete when it names a specific,
   supported vulnerability—or states that none exists.
4. **Crux** — Name the exact premise, definition, value, or missing fact that
   explains the distance between the readings. Complete when resolving it would
   materially collapse that distance.
5. **First-principles check, when triggered** — If the crux contains a
   supposedly fixed constraint (such as "must use X," "too expensive," "can't
   scale," or "that's how it is done"), or a solution justified mainly by
   analogy or authority, run the grounding pass below. Otherwise skip it.
6. **Convergence** — Recommend the most robust next formulation. Preserve the
   steel read's value while repairing the stress read's supported vulnerability.
   Complete when it states what was preserved, repaired, or left unresolved;
   derive it from grounded primitives when the check ran.
7. **Next question** — Ask one question whose answer resolves the crux. Do not
   ask a downstream question while its prerequisite remains unsettled. Complete
   when answering it would settle the current crux.
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

Use this as one bounded pass, separate from the six interpretation fields. Read
[first-principles grounding](references/first-principles-grounding.md) when the
check is triggered. It defines the constraint classes, primitive reduction,
rebuild, residuals, and kill test. Keep the main response's `Grounding` line
compact and concrete. Reserve the pass for a false-constraint or borrowed-
solution signal; keep time-critical incidents and ordinary polish on their
direct path.

## Protect the inquiry

- Ground every interpretation in the user's expressed language and context;
  leave unstated motives, personality, emotions, and beliefs outside the frame.
- Weight the steel and stress reads according to their evidence.
- Let convergence endorse one reading, revise both, preserve an explicit
  disagreement, or abstain pending evidence or a prototype.
- Route a factual dispute to the named check that could resolve it.
- When no plausible stress read exists, say so and move to the next unresolved
  decision.
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
new evidence and treat the previous convergence as provisional. Continue until
one of these conditions holds:

- the user explicitly accepts a formulation and no material crux remains;
- the remaining difference is an acknowledged value choice;
- a named fact, experiment, or prototype must come next;
- the user stops or changes the task.

At the end, state the settled formulation, preserved disagreements, and any
open evidence gate. Wait for the user's explicit request before planning or
acting on the result.
