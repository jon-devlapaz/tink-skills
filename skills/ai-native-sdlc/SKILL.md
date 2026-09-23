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
The installed operator guide is `_system/SDLC.md`. Verification starts unconfigured;
populate it with real project checks before relying on passing receipts. Repeated
initialization preserves that configuration. Initialization is not an upgrade mechanism;
compare a fresh temporary installation to plan migrations separately, and keep factory
templates untouched during active runs to preserve stage contracts.

## Workflow

1. **Locate and resume.** Read the target checkout's `AGENTS.md`, then run
   `_system/scripts/status.sh`. Select the existing run matching the request;
   inspect its `run.json` and status before creating anything. Commands operate
   on the checkout containing the scripts, not an arbitrary application repository.
   Resolve ambiguous target checkouts before mutations.
2. **Choose the entry point.** For new work, select the profile justified by scope:
   `light` combines definition in `brief.md`; `full` separates intent, spec, and
   plan for consequential changes. Maintain the selected profile across stages so
   that required review gates remain enforced. Consult [stage navigation](references/lifecycle-stages.md)
   for initialization and the active contract. Legacy drafts are not approved
   evidence; preserve them and follow repository recovery procedures.
3. **Read the active contract.** Load its immediate inputs and requested references,
   then complete that stage's work. Answer read-only questions directly without
   creating a run or walking unnecessary stages. Surface material findings immediately.
   When references conflict, disclose the discrepancy and resolve it against user
   instructions and repository policy before acting, rather than inventing an ad-hoc rule.
4. **Execute within authority.** Use a separate worktree or clone for each
   code-writing run, keeping run artifacts inside that checkout. Record only genuine
   human review decisions with the CLI, including reviewer, source, and reason.
   Prior explicit authorization remains valid within its scope; role boundaries
   must reflect actual stakeholder input rather than fabricated sign-offs. For
   capability gaps, consult [toolchain routing](references/toolchain-routing.md).
5. **Verify and report.** When the active stage or changed candidate requires
   verification, inspect `_system/verification.json` before claiming what it proves:
   new installations require project-specific checks. Run
   `_system/scripts/verify.sh <slug>`, then check current status. The generated
   receipt is `runs/<slug>/04-test/output/verification.json`. If verification is
   not required, inspect status directly. Report the completed action, evidence,
   next valid action, and any external approval or deployment result still missing.
   Local test receipts certify local checks, not deployment.

## Evidence and recovery

- Consult `_system/SDLC.md` and `python3 _system/scripts/sdlc.py <command> --help`
  for commands and recovery. The `decide` command requires `--reviewer`, `--source`,
  and `--reason` for both approval and `changes-requested`, across full-profile stages 1, 2, and 3.
- Local references are recorded, not authenticated. Hashes detect differences
  against recorded inputs; agent-writable receipts and test locks are not a
  security boundary. Trusted CI and forge policy must enforce release authority.
- Verification tolerates a stable dirty working tree, but any tracked content
  change stales prior evidence; evidence-only commits preserve content validity.
  Commit code before final verification and re-verify after any subsequent edits or
  skill mutations. The checkout fingerprint covers tracked repository files,
  not ignored files or external services.
- When work is rejected or inputs become stale, retain prior feedback, revise the
  artifacts, obtain renewed review decisions, and rerun verification. State
  transitions depend on valid receipt hashes; advance status only through the CLI,
  never by hand-editing generated receipts.
- For bug runs, demonstrate the expected failure and obtain independent acceptance
  before recording a reproduction baseline. Modifications to protected reproduction
  files fail verification against that baseline. If a recorded baseline is incorrect,
  link a replacement run under independent review. Revise implementation code to
  satisfy the contract rather than weakening test assertions to force passing receipts.
- On a busy or interrupted operation, inspect the reported lock and confirm no
  writer remains before removing it. Preserve partial results and inspect state
  before retrying; an operation's failure does not establish that nothing changed.
- Monitoring and deployment are external integrations, not provisioned capabilities.
  Follow the maintenance contract only when relevant to an explicitly configured
  intake. Prune ephemeral skills only at run closure after review and rework.
