# Experimental Jev fit decisions

Load for an explicitly requested Jev-assisted scouting run. Jev assesses
workflow fit; Scout still owns evidence collection, the other five gates,
ranking, and explanation. The helper validates recorded decisions, not the
truth or completeness of supplied evidence. This path is experimental: no
default confidence threshold or demonstrated quality improvement is assumed.

## Prepare

1. Check known disqualifiers first. Skip the call for an already rejected
   candidate. Preserve the source ladder, lineage limits, and approvals in
   [scouting-workflow.md](scouting-workflow.md).
2. Confirm that the current request authorizes model calls and transmission of
   this evidence to TypeSafe. Reuse existing authorization within its scope.
   Public research permission alone does not authorize uploading private data.
   If calls are forbidden, use ordinary Scout and do not report a Jev result.
3. Write a packet and a frozen policy outside the skill payload, in a local
   run directory. Keep credentials out of both. Preserve the original inputs
   alongside receipts; protect private evidence using the workspace's normal
   access controls.

Packet shape (all fields required; arrays may be empty except inputs/outputs):

```json
{
  "schema_version": 1,
  "contract": {
    "transformation": "Turn incident evidence into a cited brief",
    "inputs": ["incident evidence"],
    "outputs": ["cited brief"],
    "constraints": ["read-only"],
    "acceptable_adaptation": "one template change"
  },
  "candidate": {
    "id": "incident-brief",
    "source_class": "supplied",
    "source": "user-supplied material",
    "skill_path": "incident-brief/SKILL.md",
    "revision": null,
    "snapshot_sha256": "sha256:REPLACE_WITH_HASH_OF_SUPPLIED_SOURCE"
  },
  "evidence": [],
  "proposed_adaptation": null,
  "unknowns": ["Citation behavior is not established yet"],
  "coverage": {"inspected": "supplied material", "omissions": []}
}
```

Replace the snapshot marker with the SHA-256 of the supplied source material.
For public repository candidates, record an exact commit in `revision`; a branch or
tag is insufficient. `source_class` is `active_project`, `library`,
`public_repository`, or `supplied`. A supplied snapshot is not proof of source
provenance. Candidate IDs use lowercase letters, digits, underscores, or hyphens.

Each evidence item has `id`, `source` (path/lines or immutable link), `kind`
(`declaration`, `implementation`, `test`, `example`, or `evaluation`), `basis`
(`observed` or `inferred`), and verbatim `text`. Preserve unfavorable evidence
and omissions. Inspecting a test is not executing it. Missing evidence stays
unknown; it is not evidence of absence.

A named adaptation has `change`, nonempty `affected_requirements`, nonempty
`evidence_ids` referencing this packet, and `within_scope_because`. Describe it
before calling; Jev cannot invent the change. Feasibility and operational
burden remain part of Scout's compatibility gate.

Policy fields:

| Field | Requirement |
| --- | --- |
| `version` | Name of the frozen experimental policy |
| `model` | Exact Jev version, such as `jev-1.13.0`; aliases rejected |
| `confidence_threshold` | Explicit finite number in `[0, 1]`; choose through a declared evaluation policy, not as a hidden default |
| `max_input_bytes` | Integer from 1 to 24000; conservative local cap on serialized state and question, not a token estimate |

Keep one run directory and policy for the whole scouting run. Do not create
new directories, rename candidates, or adjust thresholds to bypass attempt
limits or seek a preferred answer. Retain the declared threshold even if this
run's outputs suggest a different one.

Complete when the packet records the relevant evidence and omissions, the
policy is fixed, and the existing authorization covers the payload.

## Decide

Run preflight with standard Python; it does not load an SDK or call a provider:

```sh
python3 /absolute/path/to/skill-scout/scripts/jev_fit.py preflight \
  --packet /absolute/run/packet.json --policy /absolute/run/policy.json
```

It returns the packet hash, policy hash, question hash, and payload byte count.
Review the actual packet, not merely its hash. The helper detects an embedded
TypeSafe key, but it is not a general secret or personal-data scanner.

Within the authorized scope, call once using the exact returned packet hash.
The live command alone requires `TYPESAFE_API_KEY` and the pinned SDK:

```sh
uv run --isolated --no-project --with typesafe-sdk==0.6.0 python3 \
  /absolute/path/to/skill-scout/scripts/jev_fit.py decide \
  --packet /absolute/run/packet.json --policy /absolute/run/policy.json \
  --run-dir /absolute/run/receipts --authorized-packet sha256:RETURNED_PACKET_HASH
```

The helper uses the TypeSafe API directly, a 15-second timeout, and zero SDK
retries. It records one attempt before contacting the provider. Each candidate
may have one further attempt with newly inspected evidence or a corrected
packet; unchanged packets are never resent. Candidate identity, user contract,
question, and policy must stay fixed within the run. Preserve both packet files.

An interrupted attempt stays pending and blocks replay. Record it as unresolved;
do not delete receipts to force another call. Provider failures, invalid output,
missing dependencies, and low confidence also remain unresolved. An explicit
switch back to ordinary Scout is a fallback, not a successful Jev decision.

Complete when the receipt is retained, or the categorical preflight error is
recorded and the candidate remains unresolved.

## Qualify and report

| Accepted Jev outcome | Workflow-fit disposition |
| --- | --- |
| `exact_fit` | Pass; continue remaining gates |
| `fits_with_named_adaptation` | Pass with the supplied adaptation recorded |
| `wrong_transformation` | Fail; exclude |
| `insufficient_evidence` | Unresolved; inspect the named gap or abstain |
| Below threshold, invalid response, or failed call | Unresolved |

Write the other gate statuses as a JSON object with exactly these keys:
`non_redundancy`, `safety_and_provenance`, `compatibility`, `maintenance`, and
`demonstrated_behavior`. Each value is `pass`, `fail`, or `unresolved`, supported
by Scout's evidence. Then validate final eligibility:

```sh
python3 /absolute/path/to/skill-scout/scripts/jev_fit.py qualify \
  --packet /absolute/run/packet.json --policy /absolute/run/policy.json \
  --run-dir /absolute/run/receipts --gates /absolute/run/other-gates.json
```

Only candidates with `eligible_for_ranking: true` may enter final ranking.
This includes the runner-up: if no second candidate is eligible, report
runner-up as n/a and describe excluded or unresolved candidates under evidence
or risks instead.
This command re-derives fit from the latest matching provider response rather
than trusting an edited fit-status field. A failed or unresolved other gate
blocks eligibility even when Jev reports exact fit. A stale packet, policy, or
receipt blocks validation. Re-run qualification if other gate evidence changes.

Exit codes: `0` means preflight succeeded, fit passed, or qualification allowed
ranking, depending on the command; `1` means a valid decision excludes or leaves
the candidate unresolved; `2` means an input, authorization, provider, or receipt
error. Always read the JSON result; no error authorizes a recommendation.

In the existing Scout report, cite source evidence for the fit assessment,
record adaptations and uncertainty, and identify the receipt. Receipt evidence
IDs are the inputs Jev saw, not its explanation. Confidence is not a guarantee
of correctness. Receipts and supplied gate statuses are local audit artifacts,
not cryptographically authenticated evidence of authorization or source truth.

Complete when every ranked candidate has a current eligible qualification
result and the ordinary Scout report explains its evidence and remaining gates.
