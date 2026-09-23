# Build Plan: Adopt `code-review` Skill

## Steps
1. Fetch and stage baseline `code-review` from library.
2. Delegate refactoring pass to Worker 2 (`cleaner-worker`) via `skill-cleaner`.
3. Verify cleaned diff, eliminate external setup references, preserve all 12 smell heuristics.
4. Register into `.agents/skills/code-review` using `tink skill add`.
5. Run integrity checks: `tink skill check`.
6. Run SDLC verification suite: `_system/scripts/verify.sh adopt-code-review`.
