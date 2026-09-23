# Spec: feat-engine — Feature Extraction, Compatibility Evaluation, and Risk Profiling Engine

**Derived from:** `runs/feat-engine/01-plan/output/intent.md`  
**Status:** draft  
**Lead Approver:** Agent: Architect (SDLC full run)  
**Date:** 2026-09-22  

---

## 1. Requirements & Functional Behavior

The `feat-engine` system provides a static, deterministic analysis pipeline for agent skill packages. It operates without executing untrusted code or invoking external network services.

### 1.1 Multi-Modal Feature Extraction (`FeatureExtractor`)
Given a root skill directory path:
1. **Frontmatter & Metadata Analysis (`SKILL.md`)**:
   - Extract YAML frontmatter delimited by `---` lines using a zero-dependency recursive descent / regex parser.
   - Parse canonical metadata attributes: `name`, `description`, `version`, `author`, `tags`, `tools`, `requires`.
   - Parse natural language skill body: extract Markdown headers (`#`, `##`), referenced tools (e.g. `read`, `bash`, `edit`, `write`), referenced skills, and embedded code blocks (`python`, `bash`, `sh`, `json`).
2. **Python Static AST Analysis (`scripts/*.py`, `*.py`)**:
   - Parse all Python source files using `ast.parse` into Abstract Syntax Trees.
   - Extract imported modules (`Import`, `ImportFrom`), resolving aliases and identifying high-risk namespaces:
     - OS & Process: `subprocess`, `os`, `sys`, `shutil`, `pty`, `multiprocessing`.
     - Network & Sockets: `urllib`, `requests`, `http`, `socket`, `ftplib`, `aiohttp`.
     - Code Execution: `eval`, `exec`, `compile`, `__import__`, `importlib`.
   - Traverse `Call` nodes to inspect invoked functions and attribute lookups:
     - Destructive calls: `shutil.rmtree`, `os.remove`, `os.unlink`, `os.rmdir`, `os.system`, `subprocess.Popen`, `subprocess.run`, `subprocess.call`.
     - Network calls: `socket.connect`, `urllib.request.urlopen`, `requests.get`, `requests.post`.
     - Environment lookups: `os.environ.get`, `os.getenv`, `os.environ[...]`.
     - File writes: `open(..., 'w')`, `open(..., 'wb')`, `open(..., 'a')`, `Path.write_text`, `Path.write_bytes`.
   - Resiliency: Syntax errors in Python scripts must be caught (`SyntaxError`), flagged as `syntax_error` anomalies in metadata, and not abort the entire extraction run.
3. **Shell Script Lexical Scanning (`scripts/*.sh`, `*.bash`)**:
   - Tokenize and scan shell scripts using regex patterns for operational indicators:
     - Destructive operations: `rm -rf`, `rm -r`, `mkfs`, `dd if=`, `chmod 777`, `chown -R`, `truncate`.
     - Network utilities: `curl`, `wget`, `nc`, `ncat`, `netcat`, `ssh`, `scp`, `rsync`.
     - Secret access: `cat ~/.ssh`, `cat ~/.aws`, `printenv`, `env`, `.env`.
     - Process & Autonomy escalation: `nohup`, `disown`, `&`, `kill`, `killall`.
4. **File System & Asset Footprint**:
   - Compute total file count, breakdown by extension (`.md`, `.py`, `.sh`, `.json`, etc.), and cumulative byte size.

### 1.2 Deterministic Vector Normalization (`VectorNormalizer`)
1. Compile extracted features into a normalized numerical and categorical vector:
   - Continuous metrics in range `[0.0, 1.0]`: `code_density`, `script_ratio`, `destructive_risk_factor`, `network_risk_factor`, `credential_risk_factor`, `autonomy_risk_factor`.
   - Discrete counts: `python_script_count`, `shell_script_count`, `total_files`, `total_bytes`.
   - Sorted categorical lists: `imported_modules`, `detected_tools`, `required_binaries`, `env_vars_accessed`.
2. Compute cryptographic fingerprint (`vector_hash`):
   - Format normalized vector dictionary with floats rounded to 4 decimal places.
   - Serialize with `json.dumps(vector_dict, sort_keys=True, ensure_ascii=True, allow_nan=False)`.
   - Digest: `sha256:<64-char-hex>`. Invariant across Python runs, operating systems, and host filesystems.

### 1.3 Harness & Runtime Compatibility Evaluation (`CompatibilityEvaluator`)
Evaluate whether the candidate skill can function within a specified agent harness profile:
1. **Built-in Harness Profiles**:
   - `pi`: Tools [`read`, `write`, `edit`, `bash`, `bg_start`, `bg_status`, `bg_kill`, `fd`, `rg`, `recall`, `subagents`, `herdr_*`]. Python 3.9+.
   - `claude`: Tools [`Computer`, `Bash`, `TextEditor`, `Read`, `Write`].
   - `codex`: Tools [`shell`, `file_viewer`, `file_editor`].
   - `generic`: Baseline POSIX shell and filesystem tools.
2. **Compatibility Rule Evaluation**:
   - **Compatible**: All required tools and runtime constraints are satisfied by the target harness.
   - **Compatible with Adaptation**: Missing tools have direct aliases or emulatable wrappers (e.g. `fd`/`rg` fallback to `find`/`grep`).
   - **Incompatible**: Essential required tools, unsupported shell syntax, or missing runtime binary requirements (e.g. Python < 3.9 incompatible with required 3.11 syntax) cannot be satisfied.

### 1.4 Multi-Factor Risk Profiling (`RiskProfiler`)
Evaluate skill safety across four orthogonal dimensions:
1. **Dimension 1: Destructive Operations (`weight: 0.35`)**:
   - Score calculated from AST destructive call frequency, shell `rm -rf` patterns, and arbitrary file write flags.
   - Redline Trigger: Root or recursive directory destruction (`rm -rf /`, `rm -rf *`, `shutil.rmtree('/')`).
2. **Dimension 2: External Network Egress (`weight: 0.25`)**:
   - Score calculated from network library imports, raw socket calls, and shell network utilities (`curl`, `wget`).
   - Redline Trigger: Raw socket listener or unencrypted exfiltration payloads.
3. **Dimension 3: Credential & Secret Exposure (`weight: 0.25`)**:
   - Score calculated from environment variable access patterns (`AWS_*`, `*_KEY`, `*_SECRET`, `*_TOKEN`), inspection of sensitive paths (`~/.ssh`, `~/.aws`, `.env`).
   - Redline Trigger: Direct access or exfiltration patterns targeting private keys or credentials.
4. **Dimension 4: Autonomy Escalation (`weight: 0.15`)**:
   - Score calculated from background process spawns, infinite loop constructs, and dynamic subagent invocation.
5. **Aggregate Scoring & Policy Gate**:
   $$\text{Risk Score} = \sum_{i=1}^{4} w_i \times s_i \quad \text{where } \sum w_i = 1.0, \quad s_i \in [0.0, 1.0]$$
   - Policy Thresholds:
     - `ALLOW`: Risk Score $< 0.30$ and zero redline triggers.
     - `WARN`: $0.30 \le \text{Risk Score} < 0.70$ and zero redline triggers.
     - `BLOCK`: Risk Score $\ge 0.70$ OR any redline trigger activated.

### 1.5 Dual Interface: CLI & Python Module
- **Python Module (`feat_engine.py`)**:
  ```python
  from feat_engine import extract_features, evaluate_compatibility, profile_risk, analyze_skill
  
  features = extract_features("skills/skill-scout")
  risk = profile_risk(features)
  compat = evaluate_compatibility(features, target_harness="pi")
  ```
- **CLI Interface**:
  ```bash
  python3 feat_engine.py <skill_path> [--json] [--check-compat <harness>] [--risk-threshold <allow|warn|block>] [--output <file>]
  ```
  - Exit Codes:
    - `0`: Analysis succeeded; risk score is within acceptable threshold.
    - `1`: File not found, invalid path, or fatal parsing error.
    - `2`: Security policy violation (`BLOCK` condition triggered).
    - `3`: Incompatibility detected with target harness (when strict flag enabled).

---

## 2. Architecture & Data Contracts

### 2.1 Core Data Contracts (Dataclasses / Dict Mappings)

```python
@dataclass(frozen=True)
class SkillMetadata:
    name: str
    version: str
    description: str
    author: Optional[str]
    tags: List[str]
    declared_tools: List[str]
    declared_requires: List[str]

@dataclass(frozen=True)
class CodeAnalysis:
    imported_modules: List[str]
    dangerous_calls: List[str]
    network_calls: List[str]
    filesystem_calls: List[str]
    env_lookups: List[str]
    shell_commands: List[str]
    syntax_errors: List[str]

@dataclass(frozen=True)
class SkillFeatures:
    path: str
    metadata: SkillMetadata
    code_analysis: CodeAnalysis
    file_counts: Dict[str, int]
    total_bytes: int
    has_python: bool
    has_shell: bool
    vector: Dict[str, float]
    vector_hash: str  # Format: "sha256:<64-char-hex>"

@dataclass(frozen=True)
class RiskFactor:
    score: float  # [0.0 - 1.0]
    weight: float
    triggers: List[str]

@dataclass(frozen=True)
class RiskReport:
    overall_score: float  # [0.0 - 1.0]
    verdict: str  # "ALLOW" | "WARN" | "BLOCK"
    factors: Dict[str, RiskFactor]
    redlines_triggered: List[str]

@dataclass(frozen=True)
class CompatibilityReport:
    status: str  # "compatible" | "compatible_with_adaptation" | "incompatible"
    target_harness: str
    supported_tools: List[str]
    missing_tools: List[str]
    adaptation_notes: List[str]

@dataclass(frozen=True)
class SkillAuditReport:
    schema_version: str  # "1.0.0"
    features: SkillFeatures
    risk: RiskReport
    compatibility: Optional[CompatibilityReport]
```

### 2.2 Canonical JSON Output Schema
```json
{
  "schema_version": "1.0.0",
  "skill_name": "skill-scout",
  "vector_hash": "sha256:7f9a8b1c4e...",
  "metadata": {
    "name": "skill-scout",
    "version": "0.1.0",
    "description": "Scout existing agent skills with evidence...",
    "declared_tools": ["read", "bash"],
    "tags": ["scout", "discovery"]
  },
  "metrics": {
    "file_counts": { ".md": 4, ".py": 1, ".json": 12 },
    "total_bytes": 45280,
    "has_python": true,
    "has_shell": false
  },
  "vector": {
    "destructive_risk_factor": 0.0,
    "network_risk_factor": 0.15,
    "credential_risk_factor": 0.05,
    "autonomy_risk_factor": 0.0,
    "code_density": 0.35,
    "script_ratio": 0.20
  },
  "risk": {
    "verdict": "ALLOW",
    "overall_score": 0.05,
    "factors": {
      "destructive_ops": { "score": 0.0, "weight": 0.35, "triggers": [] },
      "external_network": { "score": 0.15, "weight": 0.25, "triggers": ["urllib.request"] },
      "credential_exposure": { "score": 0.05, "weight": 0.25, "triggers": ["os.environ.get('TYPESAFE_API_KEY')"] },
      "autonomy_escalation": { "score": 0.0, "weight": 0.15, "triggers": [] }
    },
    "redlines_triggered": []
  },
  "compatibility": {
    "status": "compatible",
    "target_harness": "pi",
    "missing_tools": [],
    "adaptation_notes": []
  }
}
```

---

## 3. Skill & Dependency Capabilities

- **Dependency Policy**: Zero external pip dependencies. Strictly Python 3.9+ standard library:
  - `ast`: Static Abstract Syntax Tree inspection for Python scripts.
  - `re`: Lexical scanning of shell scripts, Markdown text, and frontmatter patterns.
  - `json`: Canonical JSON serialization and schema output.
  - `hashlib`: Invariant SHA-256 vector hashing.
  - `dataclasses`: Strongly-typed internal data contracts.
  - `pathlib`: Cross-platform filesystem navigation.
  - `typing`: Type annotations.
  - `argparse`, `sys`, `os`: CLI argument handling and execution environment.
- **Skill Integration**:
  - `skills/feat-engine/SKILL.md`: Operates as an offline tool skill guiding an agent on how to statically vet candidate skills before downloading, installing, or executing them.
  - Interoperable with `skills/skill-scout` as the automated feature extractor for candidate qualification.

---

## 4. Flagged Policy & Design Concerns (Interrogation & Jev Risk Analysis)

In accordance with `grill-me-with-jev` protocol, four critical architectural decisions were evaluated. We ran TypeSafe Jev evaluations (`jev-1.13.0`) over the decision states using Choice, Score, and Noul probes.

### 4.1 Decision Ledger & Evaluation Findings

| Decision ID | Topic | Alternatives | Jev Judgment & Confidence | Selected Architecture & Rationale |
|---|---|---|---|---|
| **D1** | **Extraction Mechanism** | A: `static_ast`<br>B: `runtime_introspection` | **Choice:** `static_ast` (P=1.00, Conf=1.0)<br>**Score:** Safety Risk of execution = 1.95/2.0 (P[Critical]=0.96)<br>**Noul:** Static sufficiency = 0.58 | **Settled on Static AST (`static_ast`).** Executing or importing untrusted scripts at vetting time carries critical risk of arbitrary code execution and sandbox escapes (Jev risk 1.95). AST parsing is completely safe, zero-side-effect, and sub-millisecond. |
| **D2** | **Vector Schema & Hashing** | A: `normalized_vector_hash`<br>B: `adhoc_attributes` | **Choice:** `normalized_vector_hash` (P=1.00, Conf=1.0)<br>**Noul:** Drift risk of ad-hoc schema = 0.95<br>**Score:** Vector robustness = 1.98/2.0 (P[Robust]=0.98) | **Settled on Normalized Vector Hash.** Ad-hoc schemas carry a 0.95 probability of breaking downstream contracts and invalidating caches. Canonical JSON serialization with SHA-256 fingerprinting provides tamper-evident stability. |
| **D3** | **Risk Profiler Architecture** | A: `multi_factor_scoring`<br>B: `single_binary_flag` | **Choice:** `multi_factor_scoring` (P=1.00, Conf=1.0)<br>**Noul:** False positive risk of binary flag = 0.95<br>**Score:** Model granularity = 1.00/2.0 (Appropriate SDLC granularity) | **Settled on Multi-Factor Scoring.** Single binary keyword matching produces 95% false positives on legitimate dev tools (e.g. `git rm`, `curl`). Orthogonal 4-factor scoring with redline overrides balances safety with developer productivity. |
| **D4** | **Dependency Policy** | A: `stdlib_only`<br>B: `external_deps` | **Choice:** `stdlib_only` (P=1.00, Conf=1.0)<br>**Noul:** Supply chain risk of 3rd party deps = 0.97<br>**Score:** Stdlib maintainability = 0.95/2.0 (Feasible with focused visitors) | **Settled on Stdlib-Only.** Adding 3rd-party dependencies to a security vetting engine introduces severe supply-chain vulnerability (0.97 Noul). Custom YAML frontmatter and AST visitors are fully maintainable within Python stdlib. |

### 4.2 Threat Model & Residual Risk Boundaries
- **Static Analysis Limits**: Static analysis cannot resolve runtime reflection (`getattr(module, obfuscated_string)`) or dynamic network payloads. Jev assessed static sufficiency at 0.58 Noul, acknowledging this theoretical limitation. To mitigate, any presence of `eval`, `exec`, or dynamic `__import__` triggers immediate escalation to `WARN` or `BLOCK`.
- **False Negatives in Shell Scripts**: Obfuscated shell commands (e.g. `base64 -d | sh`) cannot be fully parsed without an emulator. The engine mitigates this by flagging piped execution constructs as high-severity autonomy/destructive risks.
- **Credential Pattern Evasion**: Custom environment variable names cannot all be predicted. The engine flags generic patterns (`*TOKEN*`, `*KEY*`, `*SECRET*`, `*CREDENTIAL*`) as credential accesses.

---

## 5. Test Plan Specifications (Stage 03 Lock-Tests)

The test suite in `tests/test_feat_engine.py` must execute via `python3 -m unittest discover -s tests` and provide 100% coverage over the following test matrices:

1. **Frontmatter Parsing Tests (`TestFrontmatterExtraction`)**:
   - Parse valid YAML frontmatter with standard fields (`name`, `description`, `version`, `tools`).
   - Parse multiline strings and YAML-style list items (`- item1`).
   - Handle edge cases: missing frontmatter, empty frontmatter, unclosed `---` fences, trailing text.
2. **Python AST Extraction Tests (`TestPythonASTExtraction`)**:
   - Detect direct imports (`import os`, `import subprocess`) and from-imports (`from urllib.request import urlopen`).
   - Detect dangerous calls (`shutil.rmtree`, `os.system`, `subprocess.run`, `eval`, `exec`).
   - Detect environment variable reads (`os.environ.get('VAR')`, `os.getenv('VAR')`, `os.environ['VAR']`).
   - Detect file write operations (`open('foo', 'w')`, `Path.write_text`).
   - Syntax error resilience: test that invalid Python syntax (e.g. `def broken(`) produces a recorded anomaly rather than an unhandled exception.
3. **Shell Script Scanning Tests (`TestShellScriptScanning`)**:
   - Detect destructive shell invocations: `rm -rf /tmp/foo`, `mkfs.ext4`, `truncate -s 0`.
   - Detect network commands: `curl -s https://...`, `wget`, `nc -l 8080`.
   - Detect secret exfiltration patterns: `cat ~/.ssh/id_rsa`, `printenv AWS_SECRET_ACCESS_KEY`.
   - Detect background processes: `nohup ./daemon &`, `kill -9`.
4. **Vector Normalization & Hashing Tests (`TestVectorDeterminism`)**:
   - Ensure `vector_hash` is strictly identical across multiple runs on the same input directory.
   - Verify ordering invariance: swapping file scan order or dictionary key insertion order does not alter `vector_hash`.
   - Validate format: regex `^sha256:[a-f0-9]{64}$`.
5. **Risk Profiler Tests (`TestRiskProfiler`)**:
   - Safe skill: read-only Markdown and simple helpers $\to$ `verdict == "ALLOW"`, score $< 0.15$.
   - Moderate skill: uses `curl` or accesses standard env $\to$ `verdict == "WARN"`, score in $[0.30, 0.70)$.
   - Malicious / dangerous skill: invokes `rm -rf /` or `eval(...)` $\to$ `verdict == "BLOCK"`, redline trigger recorded.
   - Configurable threshold overrides: verify custom thresholds adjust the gate as expected.
6. **Compatibility Evaluator Tests (`TestCompatibilityEvaluator`)**:
   - Check compatibility against harness `pi`, `claude`, `codex`.
   - Validate detection of missing required tools and adaptation suggestions.
7. **End-to-End CLI & Repository Integration Tests (`TestFeatEngineE2E`)**:
   - Run `feat_engine.py` against existing repo skills: `skills/skill-scout`, `skills/grill-me-with-jev`, `skills/ai-native-sdlc`.
   - Verify CLI options (`--json`, `--check-compat`, `--risk-threshold`) and exit codes (`0`, `1`, `2`, `3`).
