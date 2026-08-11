# Interaction examples

Use these examples to calibrate the shape of the response. Adapt the depth to
the user's subject and language.

## Ambiguous product claim

User answer:

> We should add team chat because customers keep asking for collaboration.

Good triangulation:

- **Faithful read:** Customers are asking for collaboration, and team chat is
  the current proposed response.
- **Steel read:** Repeated collaboration demand may justify an in-product
  communication surface that keeps work and discussion together.
- **Stress read:** "Collaboration" may describe comments, approvals, presence,
  or sharing rather than chat; the proposed feature may be substituting a
  familiar solution for an unverified need.
- **Crux:** Whether customers need synchronous conversation or a different
  coordination mechanism.
- **Convergence:** Validate the collaboration job before committing to chat;
  retain chat as one candidate rather than the requirement itself.
- **Next question:** What are customers trying to accomplish when they ask for
  collaboration?

## Factual claim with missing evidence

User answer:

> MongoDB should replace Postgres because our writes are slow.

Preserve the database choice as a hypothesis, name the absent measurement, and
ask for or perform the next diagnostic check. A valid convergence can be:
"Treat datastore replacement as unproven until the write bottleneck is
localized."

## Fixed constraint with a borrowed solution

User answer:

> We have to use a queue because real-time updates cannot scale.

Use the first-principles lens only because the claimed scale constraint is doing
the work:

- **Faithful read:** Real-time updates are considered incompatible with the
  required scale, so a queue is proposed as the remedy.
- **Steel read:** A queue may absorb bursts and decouple producers from slower
  consumers, which could protect a real capacity limit.
- **Stress read:** "Cannot scale" may be an analogy or unmeasured assumption;
  the actual limit could be fan-out, connection count, payload size, or an
  implementation detail, and a queue may add latency without solving it.
- **Crux:** Which measured capacity bound makes direct updates fail, and whether
  the queue addresses that bound.
- **Grounding:** Classify the scale claim as a measured fact only if supported
  by load data; retain the required update rate and latency budget as primitives;
  reopen the queue-as-requirement assumption; rebuild the smallest transport
  that meets those bounds; kill-test it with a representative load.
- **Convergence:** Treat the queue as one candidate architecture, not a binding
  requirement, until the failing capacity and the queue's effect on it are
  measured.
- **Next question:** What load test or production measurement shows the first
  capacity bound being exceeded?

## Value conflict

User answer:

> Anonymous use protects privacy, but removing it would reduce abuse.

Differentiate the values and leave their priority with the user. A convergence
may define a reversible boundary—such as anonymous reading with rate-limited or
verified high-impact actions—only if it follows from the stated product context.
Otherwise preserve the privacy-versus-abuse choice and ask which actions create
unacceptable harm.

## No plausible stress read

User answer:

> Every production migration needs a named owner, a tested rollback, and an
> observable success condition.

State that the answer is already bounded and testable, note any genuinely
missing scope only if relevant, and move to the next unresolved decision.

## No substantive answer

User answer:

> Thanks, that makes sense.

Acknowledge normally. Continue only if the prior inquiry still has an unresolved
question.
