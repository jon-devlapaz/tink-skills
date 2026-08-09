# Tink integration

Load this adapter only when Tink is available, or when the user asks about Tink
projects, libraries, skillsets, or GitHub inspection. Skill Scout must remain
useful without Tink.

## Ownership boundary

| Owner | Responsibility |
| --- | --- |
| Skill Scout | Interpret the workflow, qualify evidence, normalize candidates, rank finalists, abstain, and define the next gate |
| Tink | Report project and library inventory, inspect GitHub skill structure, enforce canonical skillset identity, and perform approved adoption |

Tink output is evidence about location, structure, and managed state. It does
not prove workflow fit, safety, maintenance, or demonstrated behavior. Never
delegate the recommendation to Tink.

## Read-only inventory

Use Tink's public CLI rather than reading its home or catalog internals:

```bash
tink skill list
tink skillset list
tink skill check
```

- `tink skill list` reports standalone skills active in the current project.
- `tink skillset list` reports receipt-backed skillsets active in the current
  project. It currently lists group names, not member names. For a shortlisted
  group returned by this command, inspect only
  `.agents/skills/<name>-skillset/*/SKILL.md` to identify its members; do not
  scan Tink home or parse private receipt or catalog formats.
- `tink skill check` validates the project skill tree; it does not rank skills.

Open broader inventory only when the user's contract calls for it:

```bash
tink skill list --catalog
tink skill list --library
tink skillset list --library
```

Catalog and library entries are reuse leads, not proof that a capability is
active in the current project. Preserve that distinction in the report.

For a public GitHub candidate, prefer:

```bash
tink inspect <github-url>
```

Use its immutable revision, skill paths, and inferred source skillsets to bound
the audit. `tink inspect` is structural discovery only: inspect shortlisted
skills for instructions, code, provenance, tests, and risk before qualifying
them. If it cannot classify an irregular repository, report the uncovered
structure and continue with bounded read-only inspection rather than guessing.

## Adoption handoff

Skill Scout proposes the exact command and waits. Run no mutation during
scouting.

For a standalone skill:

```bash
tink skill add <source> --skill <name>
```

When `<source>` is an unambiguous local skill directory or canonical library
name, omit `--skill`. For a skillset, require its explicit canonical
`<name>-skillset` identity and a pre-authored Tink catalog definition before
proposing:

```bash
tink skillset add <name>-skillset
```

After an approved adoption, validate the resulting project state with:

```bash
tink skill check
```

Do not manually copy or symlink around Tink, synthesize catalog metadata, hide
canonical names, or bypass overwrite and drift refusals. If Tink lacks a needed
operation, expose that gap as the next product or workflow decision.
