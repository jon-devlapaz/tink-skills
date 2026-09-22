# Stage navigation

Resolve the following paths from the target workspace checkout, not this skill's
folder. Read only the active contract and its immediate inputs. Stage contracts
own outputs and gates; this index does not duplicate them.

| Work | Contract |
|---|---|
| Definition, including a light run's brief | `stages/01-plan/CONTEXT.md` |
| Design | `stages/02-design/CONTEXT.md` |
| Implementation planning and execution | `stages/03-build/CONTEXT.md` |
| Verification and failed-check recovery | `stages/04-test/CONTEXT.md` |
| Review and external release gates | `stages/05-deploy/CONTEXT.md` |
| Optional maintenance intake | `stages/06-maintain/CONTEXT.md` |

For a new run, after checking existing runs:

```sh
_system/scripts/new-run.sh <slug> --profile <light-or-full> --kind <feature-or-bug>
_system/scripts/status.sh <slug>
```

For an existing run, inspect `runs/<slug>/run.json` and status; do not infer the
profile from folder names. Light runs record the combined definition decision at
stage 3; full runs record stages 1, 2, and 3 in order.

Use `_system/SDLC.md` for decision, reproduction-lock, and verification examples
(authoritative post-install; `README.md` is its pre-packaging source-workspace equivalent).
Use CLI help to check required arguments. Paths and commands are relative to the
workspace root unless an absolute script path is supplied.

When entering review, compare the stage contract with `_shared/REVIEW.md`. Resolve
any disagreement over required review passes explicitly; do not silently weaken
a policy or edit factory references during an active feature run.
