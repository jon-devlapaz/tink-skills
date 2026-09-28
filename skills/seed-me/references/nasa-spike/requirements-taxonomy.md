# Requirements Taxonomy

Use this taxonomy whenever the router handles vague requests, requirements review, verification planning, or validation planning.

## Categories

- Goal: broad desired outcome or direction.
- Objective: measurable target or success threshold, but not necessarily an obligation on a specific artifact.
- Requirement: specific, necessary, testable obligation with a subject, condition, required behavior, acceptance signal, trace source, and verification method.
- Constraint: externally imposed limit on solution space.
- Assumption: unconfirmed statement that affects scope, acceptance, schedule, or evidence.
- Implementation choice: design, tool, architecture, library, UI pattern, data model, or approach selected to satisfy requirements.
- Acceptance criterion: observable condition used to judge whether a requirement is met.
- Verification method: test, inspection, analysis, or demonstration used to prove a requirement.
- Validation signal: evidence that the result fits intended use or ConOps.

## Router Rule

Do not convert goals or objectives into requirements until they become specific, necessary, testable obligations. Do not convert implementation choices into requirements unless the user or source makes them constraints.

Source context: `.agents/skills/requirements-distiller/references/source-grounding.md`, `.agents/skills/requirements-auditor/references/source-grounding.md`, and Appendix C pages `extraction/pages/page_207.md` through `extraction/pages/page_209.md`.
