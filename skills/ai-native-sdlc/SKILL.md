---
name: ai-native-sdlc
description: Install the SDLC scaffold into an explicitly selected project and operate its runs using stage contracts and local evidence tooling. Use when asked to set up this workflow, create or resume a run, record an actual review decision, or verify and recover a run. Not for general coding tasks or standalone Tink skill management.
license: MIT
---

# AI-Native SDLC

Advance the next authorized action in this local ICM-inspired workflow. Stage contracts
own the process; local receipts track evidence, not authenticated release authority.

## Bootstrap

Only bootstrap when setup is requested or necessary within the authorized task.
Read the target's existing instructions and select its isolated checkout first.
Invoke this skill's `scripts/init.py` by its actual path with an explicit target:

```sh
python3 <skill-directory>/scripts/init.py <target-checkout> --check
python3 <skill-directory>/scripts/init.py <target-checkout>
```

The preview reports collisions; the installer refuses unmanaged, partial, modified,
or different-version scaffolds instead of overwriting them. There is no `--force`.
The installed guide is `_system/SDLC.md`. Verification starts unconfigured and
must be given real project checks. Repeated initialization preserves that config.
For upgrades, compare a fresh temporary installation and review migration separately;
never treat initialization as an upgrade or change factory files during an active run.

## Workflow

1. **Locate and resume.** Read the target checkout's `AGENTS.md`, then run
   `_system/scripts/status.sh`. Select the existing run that matches the request;
   inspect its `run.json` and run status before creating anything. Commands operate
   on the checkout containing the scripts, not an arbitrary application repository.
   If the requested target is unclear, resolve it before mutations.
2. **Choose the entry point.** For new work, use the profile justified by the
   user's scope: `light` combines definition in `brief.md`; `full` separates
   intent, spec, and plan for consequential changes. Do not silently downgrade a
   selected profile. Consult [stage navigation](references/lifecycle-stages.md)
   for initialization and the active contract. Legacy drafts are not approved
   evidence; preserve them and follow the repository's recovery instructions.
3. **Read the active contract.** Load its immediate inputs and requested references,
   then complete that stage's work. Do not replay all six stages or create a run
   merely to answer a question. Surface material findings immediately. If references
   conflict, disclose the conflict and resolve it against user instructions and
   repository policy before the affected action; do not invent a new rule here.
4. **Execute within authority.** Use a separate worktree or clone for each
   code-writing run. Keep run artifacts in that checkout. Record only actual human
   decisions with the CLI, including reviewer, source, and reason. Prior explicit
   authorization remains valid within its scope; never fabricate a separate role's
   sign-off. For a capability gap, read [toolchain routing](references/toolchain-routing.md).
5. **Verify and report.** When the active stage or changed candidate requires
   verification, inspect `_system/verification.json` before claiming what it proves:
   new installations require project-specific checks. Run
   `_system/scripts/verify.sh <slug>`, then check current status. The generated
   receipt is `runs/<slug>/04-test/output/verification.json`. Otherwise, check
   current status without running verification. Report the completed action,
   evidence, next valid action, and any external approval or deployment result
   still missing. A passing local receipt does not mean deployed.

## Evidence and recovery

- Use `python3 _system/scripts/sdlc.py <command> --help` for current arguments;
  use `_system/SDLC.md` for commands and recovery (the installed operator guide).
  `decide` requires `--reviewer`, `--source`, and `--reason` for both approval
  and `changes-requested`, including full-profile stages 1, 2, and 3.
- Local references are recorded, not authenticated. Hashes detect differences
  against recorded inputs; agent-writable receipts and test locks are not a
  security boundary. Trusted CI and forge policy must enforce release authority.
- A stable dirty working tree can verify. Covered content changes make evidence
  stale; evidence-only commits preserve content validity. The recorded commit is
  provenance, not CI approval for a newer revision. Commit code before final
  verification and recheck after edits or skill mutations. Do not claim ignored files or external services
  are covered by the checkout fingerprint.
- On rejection or stale inputs, retain feedback and artifacts, revise the affected
  work, renew required human decisions, and rerun verification. Never hand-edit
  generated receipts to advance status.
- For bug runs, demonstrate the expected failure and obtain independent acceptance
  before recording a reproduction baseline. A changed protected file fails against
  that baseline. An incorrect already-recorded baseline needs independent review and a
  replacement run linked to the original. A rejected proposal that is not yet
  locked can be revised before acceptance; never weaken tests to obtain green.
- On a busy or interrupted operation, inspect the reported lock and confirm no
  writer remains before removing it. Preserve partial results and inspect state
  before retrying; an operation's failure does not establish that nothing changed.
- Monitoring and deployment are external integrations, not provisioned capabilities.
  Follow the maintenance contract only when relevant to an explicitly configured
  intake. Prune ephemeral skills only at run closure after review and rework.
