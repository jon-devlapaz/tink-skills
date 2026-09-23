---
name: feat-engine
description: >
  Statically extract normalized feature vectors, profile multi-factor execution
  risks, and evaluate harness compatibility for agent skills without third-party
  dependencies. Use when analyzing untrusted or new skills, auditing capabilities,
  or gating skill adoption in workflows.
---

# Feat Engine

**Feat Engine** provides standard-library-only static feature extraction, multi-factor
risk profiling, and harness compatibility evaluation for AI agent skills.

**Invariant:** Feat Engine is strictly static and read-only. It never executes
untrusted skill code, executes shell scripts, or makes network calls. It inspects
`SKILL.md`, AST nodes from Python scripts, and lexical tokens from shell scripts to
derive deterministic vectors and evaluate risk boundaries.

## Audit Workflow

When evaluating a candidate skill (e.g. under `skills/<name>` or an untrusted external directory):

1. **Run Static Audit**:
   Execute `feat_engine.py` against the target skill directory:
   ```sh
   python3 feat_engine.py <skill_dir> --json --check-compat pi
   ```
2. **Evaluate the Risk Verdict**:
   - **ALLOW** (`score < 0.30`, no redlines): Safe for adoption; conforms to static boundaries.
   - **WARN** (`0.30 <= score < 0.70`, no redlines): Contains network imports or sensitive environment variable lookups. Review findings before adopting.
   - **BLOCK** (`score >= 0.70` or redline triggered): Contains critical threats (dynamic code evaluation, root filesystem operations, raw secret exfiltration). Do not adopt or execute without remediation.
3. **Verify Harness Compatibility**:
   Confirm whether declared tools match the target harness (`pi`, `claude`, `codex`, `generic`). If `incompatible`, review missing tools before continuing.

## Architecture

The engine runs as a multi-stage static analysis pipeline:

```
Skill Directory (SKILL.md, *.py, *.sh)
                 │
                 ├── 1. parse_frontmatter() ── YAML frontmatter (name, tools, metadata)
                 ├── 2. analyze_python_code() ── AST imports, dangerous calls, env lookups, writes
                 └── 3. scan_shell_script() ── Lexical tokens (destructive, network, creds, autonomy)
                                 │
                                 ▼
                 extract_features()
                 ├── Asset metrics (file counts, total bytes)
                 ├── 8D continuous normalized vector [0.0 - 1.0]
                 └── Canonical sha256:<hex> vector hash
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
          profile_risk()              evaluate_compatibility()
    - destructive_ops (0.35)           - Target harness: pi, claude, codex, generic
    - external_network (0.25)          - Tool presence check
    - credential_exposure (0.25)       - Missing tool detection
    - autonomy_escalation (0.15)       - Compatibility verdict
    - Critical redline triggers
    - ALLOW / WARN / BLOCK
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                         analyze_skill()
                   Unified SkillAuditReport
```

### Risk Factors & Weights

| Factor | Weight | Scope |
| --- | --- | --- |
| `destructive_ops` | 0.35 | `shutil.rmtree`, `os.system` removals, `rm -rf`, `truncate`, `dd if=` |
| `external_network` | 0.25 | `urllib`, `requests`, `socket`, `curl`, `wget`, `nc` |
| `credential_exposure` | 0.25 | Private keys (`~/.ssh`, `id_rsa`), `.env`, secret tokens, passwords |
| `autonomy_escalation` | 0.15 | `nohup`, backgrounding `&`, `kill -9`, daemon processes |

### Critical Redlines

Any critical redline immediately produces a `BLOCK` verdict and forces `overall_score >= 0.70`:
- Destructive commands against root/system filesystems (`rm -rf /`, `shutil.rmtree('/')`)
- Dynamic code evaluation (`eval`, `exec`)
- Raw credential exfiltration via network utilities (e.g. `cat ~/.ssh/... | nc ...`)

### Verdicts

- **ALLOW**: Overall score `< 0.30` and no redlines triggered.
- **WARN**: Overall score `0.30 <= score < 0.70` and no redlines triggered.
- **BLOCK**: Overall score `>= 0.70` or any redline triggered.

## CLI Command Reference

```sh
# Basic summary audit of a skill
python3 feat_engine.py <skill_dir>

# JSON output with harness compatibility check
python3 feat_engine.py <skill_dir> --json --check-compat pi

# Check compatibility against another harness
python3 feat_engine.py <skill_dir> --check-compat claude

# Custom risk threshold gating
python3 feat_engine.py <skill_dir> --risk-threshold 0.50

# Save audit report to file
python3 feat_engine.py <skill_dir> --json --output audit.json
```

### Options

| Flag | Argument | Description |
| --- | --- | --- |
| `skill_path` | Positional | Directory path of the agent skill to analyze |
| `--json` | Flag | Output full audit report as formatted JSON |
| `--check-compat` | `[HARNESS]` | Evaluate compatibility against harness (`pi`, `claude`, `codex`, `generic`; default: `pi` when flag is given without argument) |
| `--risk-threshold` | Float | Score threshold above which the skill is blocked (default: 0.70) |
| `--output` | Path | Write report to file instead of stdout |

### Exit Codes

| Exit Code | Meaning |
| --- | --- |
| `0` | Pass / Allow (risk within threshold; compatible if compatibility check requested) |
| `1` | Invalid path, missing `SKILL.md`, or parse error |
| `2` | Blocked by risk policy (overall score $\ge$ threshold or redline triggered) |
| `3` | Incompatible with target harness (missing required tools; only when `--check-compat` is specified) |

## Python API

```python
import feat_engine

# High-level unified audit
audit = feat_engine.analyze_skill("/path/to/skill", target_harness="pi")
report_dict = audit.to_dict()

# Feature extraction & deterministic hashing
features = feat_engine.extract_features("/path/to/skill")
print(features.vector_hash)  # sha256:<64-char-hex>

# Risk profiling
risk = feat_engine.profile_risk(features)
print(risk.verdict)        # ALLOW, WARN, BLOCK
print(risk.overall_score)  # 0.0 - 1.0

# Compatibility evaluation
compat = feat_engine.evaluate_compatibility(features, target_harness="pi")
print(compat.status)       # compatible, incompatible

# Low-level AST & lexical parsers
fm, body = feat_engine.parse_frontmatter(skill_md_content)
py_analysis = feat_engine.analyze_python_code(python_source)
sh_analysis = feat_engine.scan_shell_script(shell_source)
```

## Security & Reliability Guarantees

1. **Strictly Static:** No file execution, dynamic imports, or process spawning of candidate code.
2. **Zero Third-Party Dependencies:** Implemented exclusively with Python 3.9+ standard library (`ast`, `hashlib`, `json`, `pathlib`, `re`, `argparse`).
3. **Cryptographic Determinism:** Canonical sorted JSON serialization guarantees byte-identical vector hashes across platforms.
