# Intent: Harden SDLC scaffold installer rollback

## Goal
Ensure `skills/ai-native-sdlc/scripts/init.py` does not leave `AGENTS.md` damaged or installer artifacts behind when initialization fails, while preserving existing project instructions and reporting the original failure clearly.

## Scope
- Track an `AGENTS.md` write attempt before performing it, and restore the original file (or remove the newly created file) if any later operation fails.
- Make rollback resilient to cleanup/restoration errors so those failures do not silently replace the initiating exception.
- Ensure lock cleanup is reliable after both successful initialization and failed rollback.
- Review the preflight/concurrent-edit check and clarify or strengthen its guarantees so a concurrent `AGENTS.md` change is not silently overwritten.
- Add focused tests for failures during/after the router write, rollback failures, lock cleanup, and concurrent modifications where feasible.

## Non-goals
- Changing scaffold contents, package format, installation policy, or automatic upgrade behavior.
- Reworking the installer into a general-purpose transaction system.
- Claiming atomic protection against arbitrary external writers unless the implementation can provide it.

## Acceptance criteria
- If writing `AGENTS.md` raises after modifying the file, the installer attempts to restore its exact original bytes; if no file existed initially, it attempts to remove the partial file.
- If a later installation step fails, created scaffold files and the router change are rolled back as far as possible.
- A rollback/cleanup failure is reported without silently obscuring the original installation failure.
- `.sdlc-init-lock` is removed on normal success and ordinary failure paths; any unavoidable cleanup failure is surfaced clearly.
- Concurrent changes to `AGENTS.md` are not knowingly overwritten; documented guarantees match the actual implementation.
- Tests exercise the failure paths and pass alongside the project’s applicable checks.

## Constraints
- Keep changes localized to the installer and focused tests unless investigation requires otherwise.
- Preserve existing installer behavior on successful installation and preview (`--check`).
- Do not stage or commit changes.
