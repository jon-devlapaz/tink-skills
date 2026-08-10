# Tink integration

Load this adapter when Tink is available or the request mentions Tink projects,
libraries, skillsets, or GitHub inspection. Skill Scout qualifies candidates;
Tink reports managed identity and performs approved adoption.

## Read-only DISCOVER inventory

Run this complete Tink pass before the online checkpoint:

```bash
tink skill list
tink skillset list
tink skill list --library
tink skillset list --library
tink skill check
```

| Surface | Meaning in Skill Scout |
| --- | --- |
| `tink skill list` | Standalone skills active in this project |
| `tink skillset list` | Receipt-backed project skillsets; listed members are active project capabilities |
| `tink skill list --library` | Reusable standalone-skill leads, not active project capability |
| `tink skillset list --library` | Reusable receipt-backed skillset and member leads, not active project capability |
| `tink skill check` | Project-tree validation only; it does not rank candidates |

If a project skillset omits members, record that inventory gap. The standalone
library commands do not expose receipt-backed skillset roots; use the skillset
command for those. Filter the full inventory against the contract and inspect
only the shortlist retained by the scouting workflow.

Resolve a selected library tree under `${TINK_HOME:-$HOME/.tink}/skills/`: a
standalone skill is `<name>/`; a skillset member is under its receipt-backed
skillset root. Read its `SKILL.md` and relevant declared references, tests, or
evaluations only. Missing or inaccessible paths are evidence gaps. Do not scan
the library recursively or inspect receipt and catalog internals.

`tink skill list --catalog` is optional cross-project history, not the default
DISCOVER pass. Run it only when the user asks for that scope; its names remain
leads rather than project capability.

## Inspecting a public repository

For a shortlisted public GitHub candidate, run:

```bash
tink inspect <github-url>
```

Use the reported immutable revision, skill paths, and inferred source skillsets
to bound read-only inspection. This establishes structure, not qualification;
inspect the shortlisted skill's instructions, code, provenance, tests, and risk
before applying Skill Scout's gates. If Tink cannot classify the repository,
record the uncovered structure and continue only with bounded read-only
inspection.

## Approved adoption handoff

Propose one exact command and wait for approval:

```bash
tink skill add <source> --skill <name>
tink skillset add <name>-skillset
```

Use the standalone form for a multi-skill source; omit `--skill` only for an
unambiguous local directory or canonical library skill name. A skillset must
use its explicit canonical `<name>-skillset` identity and pre-authored catalog
definition. Never replace this managed handoff with a copy, symlink, synthesized
catalog metadata, or bypass of overwrite and drift refusals.

After approved adoption, validate with:

```bash
tink skill check
```

If Tink lacks the needed operation, report that product or workflow decision.
