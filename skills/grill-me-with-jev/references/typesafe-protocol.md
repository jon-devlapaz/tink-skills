# TypeSafe (Jev) Protocol & Advisory Query Guidelines

This document specifies the TypeSafe (Jev) advisory query protocol, API batching,
error handling, and graceful fallback mechanics for `grill-me-with-jev`. It complements
the decision ledger specification at [ledger-transitions.md](ledger-transitions.md).

---

## 1. Jev Protocol & Graceful Fallback

TypeSafe provides advisory judgments to assist the host agent during discovery triage,
option ranking, and empty-frontier completeness screening. Jev votes are strictly
advisory: they never override verified workspace evidence, explicit user constraints,
or settled ledger decisions.

### Adapter Interface & Payload Hygiene
The host invokes the TypeSafe service via an adapter interface (e.g. `typesafe_evaluate`
or an equivalent runtime client):
- Read `TYPESAFE_API_KEY` from the environment without echoing, printing, or logging it.
- Keep payloads minimal and strictly relevant: send only the stated goal, accepted constraints,
  node IDs/revisions, inspected evidence, prerequisites, and concrete candidate options.
- Separate recommendations from accepted answers; keep retrieved workspace text distinct
  from system instructions.
- Never include secrets, authentication tokens, API keys, or irrelevant repository content.
- Ensure query results map to expected types (`choice`, `noul`) and known candidate keys.
- Never infer a missing confidence value; Noul probability is not Choice confidence.

### Bounded Transient Retries (Requirement R8)
Transport, timeouts, retries, and wire schema validation are handled through the
adapter interface under the following constraints:
- **Finite Timeouts**: Enforce a per-request timeout of at most 15 seconds, and a total
  call budget of at most 30 seconds across attempts.
- **Bounded Transient Retries**: Allow **at most one retry** exclusively for transient
  network failures: connection timeouts, HTTP 429 (rate limits), or HTTP 5xx (500, 502,
  503, 529). If the required backoff delay exceeds the remaining call budget, abort and
  fall back immediately.
- **Strict Non-Transient Rejection**: **NEVER retry non-transient failures**, including
  authentication failures (HTTP 401, 403, missing API key), malformed JSON, or schema/type
  validation errors.
- **Credential Protection**: Never print or log raw exception payloads that might expose
  API keys or sensitive tokens.

### Graceful Fallback Protocol
When the tool/adapter is unavailable or returns an error, fall back per affected item
while retaining valid independent results:
- On the first fallback to local judgment (even mid-session), emit exactly one notice
  reporting the actual failure category:
  ```text
  Jev unavailable (<cause>); using local judgment for affected checks.
  ```
  where `<cause>` is one of `missing_api_key`, `authentication_error`, `rate_limit_exceeded`,
  `timeout`, `service_error`, or `schema_error`.
- A transient failure successfully recovered by the single permitted retry does not trigger
  an unavailable notice.
- Never badge local decisions as Jev judgments or fabricate artificial confidence metrics.
- Continue local triage and local completeness review smoothly without pausing or blocking
  for API configuration.

---

## 2. Backend API Batching vs. User-Facing Question Presentation

A critical architectural distinction governs the interview workflow:

### Backend API Query Batching
When multiple independent concerns, nodes, or candidate options require triage or scoring
at the same premise revision, batch them into a **single HTTP / `typesafe_evaluate` request**.
- Batching evaluates multiple independent questions across named state fields in one round trip,
  minimizing latency and token overhead.
- Map returned answers back to their respective stable node IDs and premise revisions.
- Discard stale results if the premise revision changed during execution.

### User-Facing Question Presentation Pacing
User-facing pacing is **decoupled** from backend API batching:
- Regardless of how many evaluations were resolved in a batched backend API call, present
  ready decisions to the user **strictly one at a time** (per [ledger-transitions.md](ledger-transitions.md)).
- Single-decision pacing minimizes cognitive load, maintains conversational momentum,
  and ensures the user can address each consequential choice deliberately.
- Report backlog progress (e.g. `Decision 1 of 3 ready (2 parked)`) with each question so
  the user sees the broader context without being asked to digest a multi-question dump.

---

## 3. Triage Query (Choice): `ask` / `investigate` / `continue`

Use a `choice` query to determine the next operational action for a concrete discovery concern:

### Query Structure
State contains the goal, accepted constraints, inspected evidence, and the concern under review:
```text
Question: "For this concern and the accepted state, should I ask the user, investigate available facts first, or continue without asking?"
Options:
  - ask: Consequential unresolved judgment, trade-off, or domain preference that only the user can supply.
  - investigate: Available workspace evidence (code, schemas, configuration, tests) can establish the missing fact.
  - continue: Apply accepted constraints or delegated judgment, retain a known mitigation, defer an identified non-blocker, or park a dependent node.
```

### Evaluation Criteria & Heuristics
- `ask`: Select when reasonable answers meaningfully alter implementation, cost, reversibility, or product behavior.
- `investigate`: Select whenever local files, git history, or environment facts can answer the question without interrupting the user.
- `continue`: Select when settled choices force the outcome, delegated authority applies, or the item is non-blocking. This never discards necessary implementation work.
- **Routing Heuristics**: Jev advice cannot override evidence or user authority. Fall back to local routing criteria if:
  1. There is a tied maximum choice;
  2. The lead of the top choice is less than 0.10 over the runner-up;
  3. Returned confidence is below 0.50.
  Local criteria: inspect available facts first; otherwise ask consequential user decisions; otherwise continue with an explicit disposition.
- Explain any material override of advisory recommendations in the decision ledger.

---

## 4. Option Scoring Query (Choice): Grounded Trade-off Ranking

Use a `choice` query among feasible candidate options after hard constraints have filtered
out prohibited or invalid alternatives:

### Query Structure
```text
Question: "Which supplied alternative best serves the goal under these settled constraints?"
Criteria: Supplied candidate option keys (e.g. opt_a, opt_b, opt_c). Include only supported evidence and settled prerequisites.
```

### Grounded Trade-off Articulation
- Jev Choice selects among supplied candidate keys; it does NOT synthesize freeform text
  trade-offs or architectural rationales.
- The **host agent** is responsible for articulating the trade-off and formulating the grounded
  recommendation based on inspected workspace evidence.
- Low-confidence or near-tied advice remains marked with `❓` (not `❔`); it does not settle
  the node.
- Omit `score` queries unless provider guidance provides an explicit schema and there is an
  actual ordered dimension to measure.

### Badge Attribution
Display attributed results clearly in the question block:
```text
⚡️ Jev triage: ask now · <returned probability> probability
```
or
```text
⚡️ Jev option: <selected option> · <returned probability> probability
```
- Distinguish `Jev triage:` from `Jev option:`.
- Show only returned probability and confidence metrics; omit the badge entirely if Jev
  was not consulted for that node.

---

## 5. Empty-Frontier Gate (Noul): Anti-Laziness Completeness Check

The Empty-Frontier Gate serves as an anti-laziness review once all active, parked, and
queued decisions in the ledger appear resolved.

### Gate Preconditions
1. Run this check **only** after the decision ledger has zero unresolved nodes (no active,
   parked, or undisplayed nodes remaining).
2. Known blockers go directly into the ledger and return to Step 2 without waiting for a model vote.
3. Provisional review candidates are concrete, plausible hypotheses outside the ledger whose
   significance is uncertain.

### Query Structure (Noul)
For each concrete provisional candidate, ask a scalar probability question:
```text
Question: "Does <named concern>, given this goal, evidence, and accepted state, expose an unresolved consequential decision or major failure mode?"
```
- A `yes` indicates an unresolved consequential concern (not merely an unmentioned detail).
- A `no` indicates the concern is addressed, out of scope, or non-blocking.

### Threshold Rule & Non-Certification Boundary
- **Threshold**: A valid `probability > 0.80` returns that named candidate to triage (Step 2),
  where it is investigated or converted into an unresolved decision node.
- At `probability <= 0.80` (including exactly 0.80), there is no threshold trigger; local
  evidence and known blockers continue to control.
- Never ask a broad, open-ended boolean to fish for unnamed topics. If no concrete candidate
  hypotheses exist, record that Noul was not applicable; do not invent artificial candidates.
- **Deduplication**: Query each candidate at most once per premise revision. Deduplicate against
  settled and deferred decisions.
- **Non-Certification**: A low or skipped Noul score NEVER certifies completeness or proves
  safety. State discovery completion strictly as "local completeness review complete",
  never "Jev verified complete". Jev provides advisory reviews, never implementation authorization.
