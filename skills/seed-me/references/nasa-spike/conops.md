# ConOps Playbook

Use for unclear intent, operating scenarios, actors, workflows, nominal paths, off-nominal paths, and concept-of-operations artifacts before coding.

## Steps

1. State the operational objective in user-visible terms.
2. Identify actors, environment, preconditions, external interfaces, constraints, and assumptions.
3. Write the nominal scenario as observable user/system behavior.
4. Write off-nominal and degraded scenarios with trigger, response, and recovery expectation.
5. Separate intended behavior from implementation approach.
6. List unresolved interfaces, assumptions, open questions, and candidate requirements.

## Output

Produce a ConOps brief with objective, actors, context, nominal flow, off-nominal flows, end state, assumptions, interfaces, candidate requirements, and validation hooks.

## Hand-Offs

Route candidate obligations to `requirements-distillation.md`. Route intended-use checks to `validation-planning.md`.
