# Decision Ledger & Frontier State Transitions

This document defines the decision ledger data model, frontier state readiness,
single-decision pacing, dependency resolution, cycle breaking, and cascading
invalidation rules for `interrogate`. It is the authoritative
specification for ledger state transitions.

## 1. Decision Ledger Data Model

The interview operates as a projection of a dependency graph (acyclic
invariant, repaired via §4 cycle handling)
known as the **decision ledger**. The agent maintains this ledger to track
investigated facts, consequential trade-offs, accepted constraints, and open
blockers. During long interviews, the decision ledger may be maintained in an
ephemeral session scratchpad or temporary working state file to avoid relying solely
on in-context memory.

### Node Fields

Each node in the ledger represents either an empirical fact to establish or a
consequential decision requiring judgment. Every node must have:

- `id`: Stable, human-readable string identifier (e.g. `auth-model`, `db-engine`, `rate-limit-storage`).
- `kind`: `decision` (consequential preference or architecture trade-off) or `fact` (empirically verifiable property).
- `status`: One of `unresolved`, `settled`, `deferred`, or `superseded`.
- `prerequisites`: Tuple or list of prerequisite node IDs that must be `settled` before this node can become ready.
- `predicate`: Optional condition expression that must evaluate to true for the branch to be active.
- `evidence`: Workspace facts, inspected paths, schema snippets, configuration keys, or explicit access limitations.
- `recommendation`: Grounded host proposal based on verified evidence and settled prerequisites.
- `answer`: Actual user choice, evidence-derived fact, or delegated choice.
- `authority`: Authority source for the answer: `user` (explicit user instruction), `evidence` (verified workspace fact), or `delegated` (scoped user delegation).
- `revision`: Premise revision number at which the node was created, updated, or settled.
- `reopen_reason`: Recorded justification when an invalidated node is reopened.
- `defer_reason`: Documented reason why a non-blocking node was postponed (stored separately for deferred nodes).
- `revisit_condition`: Explicit condition or trigger under which a deferred node will be revisited (stored separately for deferred nodes).

Record default behaviors and engineering conventions as labeled **assumptions**,
never as user answers. Fact nodes resolve through verified workspace evidence;
consequential decisions strictly require explicit user choice or scoped delegation.

### JSON serialization (`ledger.json`)

The ledger is also kept as machine-readable JSON — the source the viewer renders
(see `assets/ledger-view.html`). Same fields as above, plus:

- `label`: short human title for the graph (ids stay stable and kebab-case).
- `question`: the one-line ask, for `decision` nodes on the frontier.
- `owner`, `gate`: decider and answer shape, per SKILL.md Step 3.
- `frontier`: ordered array of ready node IDs at the top level (presentation order).
  Ready = `unresolved` and listed here; parked = `unresolved` and absent.
- `revision`, `goal`: top-level ledger revision number and session goal.
- `origin`: the ID of the confirmed working draft's goal node — the first agreed
  beginning after investigation, and the graph's gravity center. The viewer roots
  its layout on this node; every later node descends from it.

The agent serves the workspace over localhost and rewrites the workspace
`ledger.json` copy each turn; counts and readiness are derived by the viewer,
never hand-written.

### Node Statuses

| Status | Meaning |
| --- | --- |
| `unresolved` | Still needs evidence or user judgment. Ready if all prerequisites are settled and activation predicates are true; otherwise parked. |
| `settled` | Fact established or actual decision accepted, with evidence or authority recorded. |
| `deferred` | Non-blocking concern intentionally postponed, with reason and revisit condition documented. |
| `superseded` | Branch no longer applies due to a changed prerequisite or false predicate; history and inactivation reason preserved. |

---

## 2. Frontier Readiness Conditions

The **frontier** is the set of unresolved nodes ready for immediate action
(investigation or user decision).

A node is **ready** if and only if:
1. Its status is `unresolved`.
2. Every prerequisite node in `prerequisites` has status `settled`.
3. Every activation `predicate` evaluates to known `true`.

### Inactive and Parked Branches
- A **false predicate** renders a branch inactive; the node is marked `superseded` (preserving history) or remains inactive.
- An **unknown predicate** keeps the node **parked** (unresolved, waiting on prerequisite evaluation).
- A **deferred prerequisite** does NOT unlock its dependents. Deferring a parent requires explicitly deferring its dependent scope as well, or retaining the dependents as parked unresolved blockers.
- Glyphs `❓` (unresolved) and `❔` (unresolved with strong grounded recommendation) follow identical readiness and transition rules.

---

## 3. Frontier Ranking & Single-Decision Pacing

To minimize user cognitive load, the workflow replaces multi-question batching
with **single-decision pacing**. When multiple independent decisions become ready
on the frontier simultaneously, they are never presented all at once.

### Ranking Priority
When multiple independent nodes are ready on the frontier, prioritize and rank
them by:
1. **Consequence**: Highest architectural, security, data integrity, or runtime behavioral impact.
2. **Risk**: blast radius × irreversibility × cost of reversal, stated in one line per node; record the tiebreak reason in the ledger.

Select the single highest-priority ready decision to present to the user.

### Presentation Format & Backlog Progress
Present exactly one decision per interaction turn in the canonical template
owned by SKILL.md Step 3 (single source; do not duplicate it here). Always report backlog progress
so the user retains visibility into total scope without feeling overwhelmed:

```text
Decision 1 of 3 ready (2 parked)
(see SKILL.md Step 3 for the canonical ❓/📜/👤/➡️ template)
```

- Report counts: `Decision X of Y ready (Z parked)` where:
  - `X`: Current question index in the ready queue.
  - `Y`: Total count of currently ready independent decisions.
  - `Z`: Count of parked nodes awaiting prerequisites or investigations.
- Undisplayed and queued ready nodes remain tracked blockers in the ledger that
  prevent completion until settled.

### Pacing Cycle
1. Select and present the single highest-ranked ready decision.
2. Wait for explicit user input before advancing the ledger.
3. Record the answer, apply scoped delegations or exclusions, and transition the node to `settled`.
4. Recompute readiness across all remaining ledger nodes.
5. Select and present the next single ready decision, or proceed to completion review if the frontier is clear.

---

## 4. Dependencies & Cycle Resolution

An edge in the ledger indicates that changing a prerequisite node could alter this
node's choice, validity, or consequence.

### Cycle Detection
Every newly introduced or modified dependency edge must be checked for cycles.
If node A requires node B and node B requires node A:
- Do NOT park both nodes indefinitely and claim an empty frontier.
- First, attempt to investigate an inspectable workspace fact that breaks the dependency.
- If factual investigation cannot break the cycle, collapse the interdependent nodes into **one joint decision** presenting feasible combinations and their collective consequences.
- If no combination is feasible, expose the conflicting constraints directly as an explicit blocker.

### Conditional Answers
Answers conditioned on external or unverified facts (e.g., “Only if hosting is under $100/mo”
or “Use Redis only if cluster mode is supported”) are **conditional answers**, not settlements:
1. Record the condition as a predicate and investigate the factual claim.
2. If verified `true`, settle the node using the user's conditional choice (`authority: user`).
3. If verified `false`, retain the failed condition and reopen the choice for user judgment.
4. An answer condition is not automatically a branch activation predicate: a false answer condition reopens the decision rather than hiding the node.
5. If the fact is inaccessible, record the access limitation and ask the user only for information they can supply.
6. Never repeat the same failed investigation without new evidence or access; preserve the blocker or stop incomplete when no forward step exists.

---

## 5. Answers, Delegation, and Deferral

### Explicit Choices & Prohibitions
- Record the actual user answer even when it contradicts the host recommendation.
- Apply volunteered constraints and prohibitions (e.g. “No Kafka under any circumstances”) across all nodes and candidate options immediately.
- If a user choice conflicts with an accepted constraint, expose the conflict explicitly rather than silently erasing prior decisions.

### Scoped Delegation
- Phrases like “whatever you think”, “you decide”, or “I don't care which option” delegate the referenced decision.
- Settle the node using the currently valid recommendation within that scope; record `authority: delegated`. Nodes marked `⚠️ ungrounded` cannot settle by delegation: retain as unresolved blockers.
- If no valid recommendation exists, investigate workspace facts or retain the node as an unresolved blocker.
- Ambiguous delegation covers only the clearly referenced node, never all future decisions.
- “Use your arrows” accepts currently displayed valid recommendation arrows (`➡️`) only.
- Worked example: “you decide” on a node with 📜 lines and a ➡️ settles it as `delegated`; the same words on a `⚠️ ungrounded` node settle nothing — it stays an unresolved blocker.
- Acceptance of an earlier recommendation does not authorize a replacement if the premise is subsequently invalidated; only continuing explicit delegation covers a revised choice.
- “I don't care” without a clear referent does not remove a requirement; clarify only if its meaning changes a consequential outcome.

### Deferrals
- “Skip this” requests deferral, not acceptance or dependency parking. Deferring a parked node requires scoping out its dependents or retaining them as parked blockers — skip never silently unblocks.
- Defer only **non-blocking** concerns, recording both a `defer_reason` and a concrete `revisit_condition`.
- If the skipped item is a known blocker, keep it `unresolved` and explain once why it cannot be deferred without compromising discovery.
- Do not repeat an explicitly skipped question without a new reason; it remains a tracked item preventing completion until settled or explicitly scoped out.

### Silence & Stopping
- Unanswered nodes remain `unresolved`; do not reprint unchanged questions repeatedly. Identify the remaining blocker once and wait for input.
- If the user asks to stop interviewing, immediately halt questioning, preserve all unresolved blockers in the ledger, and report `stopped — incomplete`.

---

## 6. Cascading Invalidation

When an accepted answer, constraint, or underlying piece of evidence changes semantically:

### 6.1 Increment Premise Revision

Increment the ledger's premise revision number and invalidate any prior pre-intent confirmation.

### 6.2 Transitive Traversal

Traverse all transitive descendant nodes in topological prerequisite order.

### 6.3 Preserve Valid Justifications

Preserve answers whose justifications remain fully supported and freshly verified at the current revision despite the changed premise.

### 6.4 Reopen Invalidated Nodes

Reopen nodes whose prerequisites or premises were altered, setting status back to `unresolved`, clearing or parking invalid answers, and recording `reopen_reason`.

### 6.5 Supersede Inactive Branches

Mark branches rendered irrelevant by changed choices as `superseded`.

### 6.6 Reactivate Superseded Branches

Re-evaluate previously superseded branches that become active under the new premise.

### 6.7 Preserve Independent Nodes

Nodes not dependent on the changed premise retain their settled status, answers, and authority intact.

### 6.8 No-Op Protection

An unchanged repeated answer is a no-op; it does not increment revision or dirty descendants.

### 6.9 Origin Is Pinned

Invalidation never moves `origin`. The origin is history — the first agreed
beginning — not current truth; reopened descendants re-derive against it via
`reopen_reason`. If the session's goal itself is replaced (not refined),
that is a new session with a new ledger, never a moved origin.

### Post-Traversal Readiness
After traversal, recompute readiness: reopened descendants remain parked until their
updated prerequisites settle. When re-asking a reopened question, explicitly state
the changed premise that prompted reopening. Reopen only for a recorded factual
or authority change, never on a hunch alone.
