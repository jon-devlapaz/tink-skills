# Specification: Adopt `code-review` Skill

## Technical Design & Boundaries

### 1. Skill Contract & Schema
- **Name**: `code-review`
- **Location**: `.agents/skills/code-review/SKILL.md` (and canonical project directory `skills/code-review/SKILL.md`)
- **Metadata**:
  - Name: `code-review`
  - Description: Two-axis review of git diffs against Standards and Specs using parallel subagents.

### 2. Runtime Boundaries & Execution Matrix
- **Harness**: Standard `pi` subagent or host agent session.
- **Tools**: Read-only git inspection (`git diff`, `git log`, `git rev-parse`) and repository read tools (`read`, `fd`, `rg`).
- **Dependencies**: No external shell setups or vendor-specific commands.

### 3. Fowler Smell Baseline (12 Preserved Heuristics)
1. Mysterious Name
2. Duplicated Code
3. Feature Envy
4. Data Clumps
5. Primitive Obsession
6. Repeated Switches
7. Shotgun Surgery
8. Divergent Change
9. Speculative Generality
10. Message Chains
11. Middle Man
12. Refused Bequest

### 4. Non-Functional Requirements
- Valid markdown structure adhering to Agent Skills spec.
- Pass `tink skill check` with 0 warnings or errors.
- Pass repository test suite in `_system/verification.json`.
