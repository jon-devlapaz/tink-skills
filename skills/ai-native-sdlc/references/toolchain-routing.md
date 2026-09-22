# Toolchain routing for a run

1. Load mandatory policy skills deterministically. Reuse an appropriate loaded
   skill before routing. Route only a real capability gap; ranking is evidence of
   fit, not trust or installation authority.
2. Consult `manage-tink` for authorized Tink operations. Use the workspace wrapper
   consistently for cooperating operations:
   ```sh
   python3 _system/scripts/sdlc.py skills tink-route -- --json "<capability needed>"
   ```
   Check the installed CLI's help and returned schema; do not assume a fixed
   activation JSON structure. The `sdlc.py skills ... --` prefix is this scaffold's
   wrapper; everything after `--` belongs to the installed CLI — treat the examples
   as illustrative and confirm against `--help`. Low confidence, an ambiguous winner, or unavailable
   routing leaves the capability unresolved; do not install an arbitrary fallback.
3. Install only within existing user authority. When authorized:
   ```sh
   python3 _system/scripts/sdlc.py skills tink-route -- -i --ephemeral --json "<capability needed>"
   python3 _system/scripts/sdlc.py skills tink -- skill check
   ```
   Inspect failures for partial writes before retrying. Validate the selected
   entrypoint is inside the intended worktree's skill root, then explicitly read
   its `SKILL.md`. JSON output and installation alone do not activate instructions.
4. Preserve routing output, selected skill source revisions/content hashes, and
   activation outcomes with the run. Keep baseline manifests under reviewed
   dependency management; temporary routing must not automatically rewrite them.
   Keep installed skills and ephemeral ledgers worktree-local. Restore baseline
   skills through Tink rather than sharing writable symlinks.
5. At run closure, after review and rework, retain provenance and preview cleanup:
   ```sh
   python3 _system/scripts/sdlc.py skills tink-route -- prune --dry-run
   ```
   Inspect the actual scope before authorized pruning through the same wrapper.
   Avoid `--all-unpinned` for routine cleanup. Pruning can invalidate checkout
   evidence and cannot remove instructions already loaded into agent context.

The wrapper serializes cooperating calls using a local user/temp-directory lock.
It does not make installation transactional, isolate shared home-library state,
or coordinate direct CLI calls, different lock namespaces, or multiple hosts.
Do not call an install atomic or infer cleanup guarantees beyond the installed
CLI's documented behavior and observed dry-run result.
