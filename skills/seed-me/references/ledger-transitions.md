# Decision Ledger & Frontier State Transitions

This document defines the decision ledger data model, frontier state readiness,
single-decision pacing, dependency resolution, cycle breaking, and cascading
invalidation rules for `seed-me`. It is the authoritative
specification for ledger state transitions.

## 1. Decision Ledger Data Model

The interview operates as a projection of a dependency graph (acyclic
invariant, repaired via §4 cycle handling)
known as the **decision ledger**. The agent maintains this ledger to track
investigated facts, consequential trade-offs, accepted constraints, and open
blockers. Persist the ledger throughout the interview using `scripts/session.py` and the
Session lifecycle in SKILL.md. Keep one `ledger.json` containing current state
and per-node history outside the repository; it is not an ephemeral scratchpad.

### Node Fields

Each node in the ledger represents either an empirical fact to establish or a
consequential decision requiring judgment. Use these JSON types when publishing;
requiredness depends on kind and status, not every field is mandatory.

| Field | Type | Requirement and meaning |
| --- | --- | --- |
| `id` | string | Required, nonempty, unique stable identifier (e.g. `auth-model`). |
| `kind` | string | Required: `decision` for judgment or `fact` for an empirically verifiable property. |
| `status` | string | Required: `unresolved`, `settled`, `deferred`, or `superseded`. |
| `prerequisites` | array of strings | Required; distinct nonempty node IDs. Use `[]` for none. Each prerequisite must be settled before this node is ready. |
| `predicate` | boolean or null | Optional; omitted means `true`, `null` means unknown. Record an observed condition, not an expression for the helper to evaluate. |
| `evidence` | array of strings (`list[str]`) | Required; each entry is nonempty text recording an inspected path, fact, schema snippet, configuration key, or access limitation. `[]` is valid except when settling by `evidence` or `delegated` authority. |
| `owner` | string | Required, nonempty for decisions: who can settle this choice. Facts need no owner. |
| `gate` | string | Required, nonempty for decisions: the answer needed to settle this choice, e.g. “Explicitly confirm this investigation goal.” This describes the interview answer, not an SDLC approval gate or executable rule. Facts need no gate. |
| `label` | string | Optional short display title. |
| `question` | string | Optional one-line ask for display. |
| `recommendation` | string | Optional grounded host proposal based on evidence and settled prerequisites. |
| `answer` | string or null | Required, nonempty when settled: actual user choice, evidence-derived fact, or delegated choice. Otherwise omit or use `null`. |
| `authority` | string or null | Required when settled: `evidence` for facts; `user` or `delegated` for decisions. Otherwise omit or use `null`. |
| `authority_source` | string or null | Required, nonempty when settled: actual user-answer/delegation reference or inspected fact source. Otherwise omit or use `null`. |
| `reopen_reason` | string | Nonempty whenever present; required when a settled node becomes unresolved. Retained in history on subsequent changes. |
| `defer_reason` | string | Required, nonempty when deferred: why this non-blocking concern was postponed. |
| `revisit_condition` | string | Required, nonempty when deferred: concrete trigger for revisiting it. |
| `revision` | integer | Helper-owned premise revision; omit from publication payloads. |
| `history` | array of objects | Helper-owned prior node states with timestamps and reasons; omit from publication payloads. |

Omit `owner` and `gate` on facts; the validator permits them but does not require
them there. Types for `label`, `question`, and `recommendation` are authoring
conventions, not validator guarantees. Clear `answer`, `authority`, and `authority_source` when
reopening; their previous values remain in history.

Record default behaviors and engineering conventions as labeled **assumptions**,
never as user answers. Fact nodes resolve through verified workspace evidence;
consequential decisions strictly require explicit user choice or scoped delegation.

### JSON serialization (`ledger.json`)

`scripts/session.py` validates and publishes the source rendered by
`assets/ledger-view.html`. `assets/ledger.json` is an empty schema example only;
`init` creates a fresh identity and timestamps for each real session.

Top-level fields:

- `schema_version`: `1`.
- `session_id`, `created_at`, `updated_at`: helper-owned identity and timestamps.
- `version`: helper-owned publication counter for optimistic concurrency.
- `revision`: premise revision; distinct from publication version and question order.
- `status`: `active`, `stopped`, or `completed`. Ended sessions are read-only.
- `draft`: candidate `goal`, `outcome`, and `options`; none is an accepted answer.
- `goal`, `origin`: initially `null`. Confirmation creates a settled user decision
  whose ID is `origin` and whose `answer` exactly equals `goal` (string equality).
  Both then remain fixed; record scope refinements in other nodes.
  A replacement goal starts a new session.
- `current_question`: one ready decision ID, or `null`; always `null` after ending.
- `nodes`: the current concerns, including their helper-owned `revision` and `history`.
- `frontier`: helper-derived ready IDs in node-list order. Unresolved nodes absent
  from it are parked. The host selects a current question using §3; it never writes
  the derived frontier directly.

Independent nodes may be unconnected; `origin` identifies the confirmed beginning,
not an artificial prerequisite.

### Publication payload

Write a proposed update to `<session>/update.json`, then invoke `publish` as in
SKILL.md. Start from a fresh `read`: retain only `status`, `draft`, `goal`, `origin`,
`current_question`, and `nodes` under `state`. Strip `history` and `revision` from
each node. The helper owns all other stored fields. Initial draft example:

```json
{
  "expected_version": 0,
  "reason": "Shape the provisional working draft",
  "state": {
    "status": "active",
    "draft": {"goal": "Candidate goal", "outcome": "Candidate outcome", "options": []},
    "goal": null,
    "origin": null,
    "current_question": null,
    "nodes": []
  }
}
```

After that draft publication, a confirmed-goal update can look like this.
This is a **synthetic example**, including its user confirmation and inspected
fixture: do not treat these strings as real authority or workspace evidence.
In a real session, settle the goal only from explicit user confirmation and
settle the fact only after inspecting its source. Copy the confirmed goal text exactly into
both `state.goal` and the origin node's `answer`.

```json
{
  "expected_version": 1,
  "reason": "Synthetic example: user confirmed investigation scope; inspected import fixture",
  "state": {
    "status": "active",
    "draft": {"goal": "Candidate goal", "outcome": "Candidate outcome", "options": []},
    "goal": "Investigate safe data import",
    "origin": "goal",
    "current_question": null,
    "nodes": [
      {
        "id": "goal",
        "kind": "decision",
        "status": "settled",
        "prerequisites": [],
        "evidence": [],
        "owner": "User",
        "gate": "Explicitly confirm this investigation goal",
        "answer": "Investigate safe data import",
        "authority": "user",
        "authority_source": "Synthetic chat turn 2: user explicitly confirmed this investigation goal"
      },
      {
        "id": "import-behavior",
        "kind": "fact",
        "status": "settled",
        "prerequisites": [],
        "evidence": ["Synthetic fixture import.py:10 calls replace(existing, incoming)"],
        "answer": "The fixture replaces existing data on import",
        "authority": "evidence",
        "authority_source": "Synthetic inspection of fixture import.py:10"
      }
    ]
  }
}
```

The origin is a user decision, so its evidence list may be empty. The settled
fact requires nonempty evidence and omits `owner`/`gate`. Neither the goal nor
the fact chooses an implementation; no decorative prerequisite connects them.

Use the actual observed `version`, not hardcoded example versions.
`reason` describes the real update. Optional `revalidated` maps affected settled
node IDs to fresh justifications; their evidence must also be populated. Evidence
truth and user authority remain host responsibilities, not validator judgments.

The helper locks each publication, rejects stale or inconsistent updates, and
atomically replaces the ledger. It appends prior node state, `superseded_at`, and
`reason` to `history`; revalidated nodes use their own revalidation justification.
Read current state by default and retrieve history for changes, not as live answers.
Exact repeated updates are no-ops. A stopped session preserves unresolved concerns;
completion also requires the host's coverage review, confirmation, and successful
pre-intent save. Empty frontier alone is not completion.

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

An edge records a real prerequisite: this concern needs that answer or fact.
Changing the prerequisite could alter the dependent choice, validity, or consequence.
Shared topics and the session goal alone do not justify edges.

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

Reopen nodes whose prerequisites or premises were altered: set status to
`unresolved`, remove `answer`, `authority`, and `authority_source`, and supply a
nonempty `reopen_reason`. Publishing retains the superseded answer in history;
never leave an invalid answer active.

### 6.5 Supersede Inactive Branches

Mark branches rendered irrelevant by changed choices as `superseded`.

### 6.6 Reactivate Superseded Branches

Re-evaluate previously superseded branches that become active under the new premise.

### 6.7 Preserve Independent Nodes

Nodes not dependent on the changed premise retain their settled status, answers, and authority intact.

### 6.8 No-Op Protection

An unchanged repeated answer is a no-op; it does not increment revision or dirty descendants.

### 6.9 Origin Is Pinned

Invalidation never moves `origin` or rewrites the confirmed `goal`. They identify
the accepted beginning. Record refinements in other concerns and revisit their
actual dependents via `reopen_reason`. Replacing the goal starts a new session,
never a moved origin. Restarting a viewer changes neither identity nor revision.

### Post-Traversal Readiness
After traversal, recompute readiness: reopened descendants remain parked until their
updated prerequisites settle. When re-asking a reopened question, explicitly state
the changed premise that prompted reopening. Reopen only for a recorded factual
or authority change, never on a hunch alone.
