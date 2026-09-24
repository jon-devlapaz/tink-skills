#!/usr/bin/env python3
"""Skill Gate - Static Feature Extraction, Multi-Factor Risk Profiling,

and Harness Compatibility Evaluator for Agent Skills.

Standard library only (zero third-party dependencies). Compatible with Python 3.9+.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

SCHEMA_VERSION = "1.0.0"

HARNESS_PROFILES: Dict[str, Set[str]] = {
    "pi": {
        "read", "write", "edit", "bash", "bg_start", "bg_status", "bg_list", "bg_kill",
        "fd", "rg", "recall", "typesafe_evaluate", "generate_image",
        "herdr_start_agent", "herdr_send_prompt", "herdr_read_agent", "herdr_wait_agent",
        "herdr_list_agents", "herdr_get_agent", "herdr_stop_agent", "herdr_rename_agent",
        "herdr_focus_agent", "herdr_explain_agent", "herdr_delegate", "herdr_split_pane",
        "herdr_run_command", "herdr_read_pane", "herdr_wait_output", "herdr_send_keys",
        "herdr_close_pane", "herdr_list_panes", "herdr_get_pane", "herdr_resize_pane",
        "herdr_zoom_pane", "herdr_move_pane", "herdr_swap_panes", "herdr_list_tabs",
        "herdr_create_tab", "herdr_get_tab", "herdr_focus_tab", "herdr_rename_tab",
        "herdr_close_tab", "herdr_list_workspaces", "herdr_create_workspace",
        "herdr_get_workspace", "herdr_focus_workspace", "herdr_rename_workspace",
        "herdr_close_workspace", "herdr_worktree_create", "herdr_worktree_open",
        "herdr_worktree_list", "herdr_worktree_remove", "herdr_api_snapshot",
        "herdr_session_list", "herdr_session_stop", "herdr_session_delete",
        "ask_user", "file_search", "dir_list"
    },
    "claude": {
        "read", "write", "edit", "bash", "glob", "grep", "view", "create",
        "str_replace_editor", "bash_command", "file_search", "web_search", "web_fetch"
    },
    "codex": {
        "read", "write", "edit", "bash", "python", "shell", "exec"
    },
    "generic": {
        "read", "write", "bash", "edit"
    }
}

SENSITIVE_ENV_PATTERNS = [
    r"SECRET", r"KEY", r"TOKEN", r"PASSWORD", r"PASSWD", r"CREDENTIAL",
    r"PRIVATE", r"AUTH", r"ACCESS_KEY", r"APIKEY", r"SIGNING"
]

BENIGN_ENV_NAMES = {
    "USER", "HOME", "PATH", "LANG", "SHELL", "PWD", "TERM", "TMPDIR",
    "EDITOR", "PAGER", "TZ", "HOSTNAME", "LOGNAME"
}


# ============================================================================
# Frontmatter Parser
# ============================================================================

def _parse_yaml_scalar(val_str: str) -> Any:
    val_str = val_str.strip()
    if not val_str:
        return ""
    if (val_str.startswith('"') and val_str.endswith('"')) or (val_str.startswith("'") and val_str.endswith("'")):
        return val_str[1:-1]
    low = val_str.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "none", "~"):
        return None
    # Inline list support: [item1, item2]
    if val_str.startswith("[") and val_str.endswith("]"):
        items = [s.strip() for s in val_str[1:-1].split(",") if s.strip()]
        return [_parse_yaml_scalar(item) for item in items]
    try:
        if "." in val_str:
            # Check if valid float (reject version strings like 1.0.0)
            parts = val_str.split(".")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                return float(val_str)
            return val_str
        if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
            return int(val_str)
    except ValueError:
        pass
    return val_str


def _parse_yaml_block(lines: List[str]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    i = 0
    n = len(lines)

    while i < n:
        raw_line = lines[i]
        line = raw_line.strip()
        if not line or line.startswith("#"):
            i += 1
            continue

        if ":" in line:
            indent = len(raw_line) - len(raw_line.lstrip(" "))
            key, sep, rest = line.partition(":")
            key = key.strip()
            rest = rest.strip()

            # Multiline string: > or |
            if rest in (">", "|"):
                block_lines: List[str] = []
                i += 1
                while i < n:
                    subline = lines[i]
                    sub_indent = len(subline) - len(subline.lstrip(" "))
                    if not subline.strip():
                        block_lines.append("")
                        i += 1
                        continue
                    if sub_indent <= indent:
                        break
                    block_lines.append(subline.strip())
                    i += 1
                if rest == ">":
                    result[key] = " ".join(b for b in block_lines if b).strip()
                else:
                    result[key] = "\n".join(block_lines).strip()
                continue

            elif rest == "":
                # Could be a list or nested dict
                i += 1
                child_lines: List[str] = []
                while i < n:
                    subline = lines[i]
                    sub_indent = len(subline) - len(subline.lstrip(" "))
                    if not subline.strip():
                        i += 1
                        continue
                    if sub_indent <= indent:
                        break
                    child_lines.append(subline)
                    i += 1

                if child_lines:
                    first_stripped = child_lines[0].strip()
                    if first_stripped.startswith("- "):
                        items = []
                        for cl in child_lines:
                            cls = cl.strip()
                            if cls.startswith("- "):
                                items.append(_parse_yaml_scalar(cls[2:].strip()))
                        result[key] = items
                    else:
                        base_indent = len(child_lines[0]) - len(child_lines[0].lstrip(" "))
                        stripped_children = [
                            cl[base_indent:] if len(cl) >= base_indent else cl
                            for cl in child_lines
                        ]
                        result[key] = _parse_yaml_block(stripped_children)
                else:
                    result[key] = ""
                continue
            else:
                result[key] = _parse_yaml_scalar(rest)
                i += 1
        else:
            i += 1

    return result


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parses YAML frontmatter fenced by `---` lines.

    Supports key-value pairs, nested lists (- item), strings.
    Returns (frontmatter_dict, markdown_body).
    Gracefully handles missing, empty, or unclosed delimiters.
    """
    if not content:
        return {}, ""

    lines = content.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, content

    closing_idx = -1
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            closing_idx = idx
            break

    if closing_idx == -1:
        # Unclosed frontmatter delimiter
        return {}, content

    fm_raw = "".join(lines[1:closing_idx])
    body = "".join(lines[closing_idx + 1:])

    if not fm_raw.strip():
        return {}, body

    try:
        frontmatter = _parse_yaml_block(fm_raw.splitlines())
    except Exception:
        frontmatter = {}

    return frontmatter, body


# ============================================================================
# Python AST Code Analysis
# ============================================================================

@dataclass
class CodeAnalysis:
    imported_modules: List[str] = field(default_factory=list)
    dangerous_calls: List[str] = field(default_factory=list)
    env_lookups: List[str] = field(default_factory=list)
    filesystem_calls: List[str] = field(default_factory=list)
    syntax_errors: List[str] = field(default_factory=list)


def _get_call_name(node: ast.AST) -> str:
    parts: List[str] = []
    curr = node
    while isinstance(curr, ast.Attribute):
        parts.append(curr.attr)
        curr = curr.value
    if isinstance(curr, ast.Name):
        parts.append(curr.id)
        parts.reverse()
        return ".".join(parts)
    return ""


def analyze_python_code(code: str) -> CodeAnalysis:
    """Uses ast.parse to extract imported modules, dangerous calls,

    environment variable accesses, filesystem write calls, and captures
    SyntaxError without throwing.
    """
    analysis = CodeAnalysis()
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        analysis.syntax_errors.append(f"SyntaxError: {e}")
        return analysis
    except Exception as e:
        analysis.syntax_errors.append(f"ParseError: {e}")
        return analysis

    imported: Set[str] = set()
    dangerous: Set[str] = set()
    env_lookups: Set[str] = set()
    fs_calls: Set[str] = set()

    DANGEROUS_TARGETS = {
        "shutil.rmtree", "os.system", "subprocess.run", "subprocess.Popen",
        "subprocess.call", "subprocess.check_call", "subprocess.check_output",
        "eval", "exec", "os.popen", "rmtree", "system"
    }

    for node in ast.walk(tree):
        # Imports
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)

        # Function Calls
        elif isinstance(node, ast.Call):
            call_name = ""
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                call_name = _get_call_name(node.func)

            if call_name:
                for target in DANGEROUS_TARGETS:
                    if call_name == target or call_name.endswith("." + target):
                        dangerous.add(call_name)

                shell_true = any(
                    kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in node.keywords
                )
                if shell_true and (call_name.startswith("subprocess.") or call_name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}):
                    dangerous.add(f"{call_name}:shell=True")

                # Environment variable lookups via calls: os.environ.get(...), os.getenv(...)
                if call_name in ("os.environ.get", "os.getenv", "environ.get", "getenv"):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        env_lookups.add(node.args[0].value)

                # Filesystem write operations
                if call_name == "open":
                    is_write = False
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                        mode = str(node.args[1].value)
                        if any(m in mode for m in ("w", "a", "x", "+")):
                            is_write = True
                    for kw in node.keywords:
                        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                            mode = str(kw.value.value)
                            if any(m in mode for m in ("w", "a", "x", "+")):
                                is_write = True
                    if is_write:
                        fs_calls.add("open:write")
                elif call_name.endswith(".write_text") or call_name == "write_text":
                    fs_calls.add("Path.write_text")
                elif call_name.endswith(".write_bytes") or call_name == "write_bytes":
                    fs_calls.add("Path.write_bytes")
                elif call_name.endswith(".write") or call_name == "write":
                    fs_calls.add("write")
                elif call_name in ("os.remove", "os.unlink", "pathlib.Path.unlink", "Path.unlink"):
                    fs_calls.add("remove")
                elif call_name in ("os.rename", "os.replace", "shutil.copy", "shutil.copy2", "shutil.copyfile", "shutil.move"):
                    fs_calls.add("file_mutation")

        # Environment variable lookups via subscript: os.environ[...] or environ[...]
        elif isinstance(node, ast.Subscript):
            base_name = _get_call_name(node.value) if isinstance(node.value, ast.Attribute) else (
                node.value.id if isinstance(node.value, ast.Name) else ""
            )
            if base_name in ("os.environ", "environ"):
                slice_node = node.slice
                if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                    env_lookups.add(slice_node.value)
                elif hasattr(slice_node, "value") and isinstance(slice_node.value, ast.Constant) and isinstance(slice_node.value.value, str):
                    env_lookups.add(slice_node.value.value)

    analysis.imported_modules = sorted(imported)
    analysis.dangerous_calls = sorted(dangerous)
    analysis.env_lookups = sorted(env_lookups)
    analysis.filesystem_calls = sorted(fs_calls)
    return analysis


# ============================================================================
# Shell Script Lexical Scanner
# ============================================================================

def _shell_scan_text(line: str) -> str:
    """Normalize shell text to reduce lexical false positives from URLs and inline comments."""
    cleaned = re.sub(r"https?://\S+", " ", line)
    cleaned = re.sub(r"#.*$", " ", cleaned)
    return cleaned


def scan_shell_script(script: str) -> Dict[str, Any]:
    """Lexical scanner for shell commands:

    - Destructive commands (rm -rf, truncate, dd if=)
    - Network utilities (curl, wget, nc)
    - Secret exfiltration (~/.ssh, .env)
    - Autonomy escalation (nohup, &, kill -9)
    Returns dictionary with boolean flags and matched token lists.
    """
    matched_destructive: Set[str] = set()
    matched_network: Set[str] = set()
    matched_credentials: Set[str] = set()
    matched_autonomy: Set[str] = set()

    lines = script.splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        scan_line = _shell_scan_text(line)
        if not scan_line.strip():
            continue

        # Destructive patterns
        if re.search(r"\brm\b(?=[^\n]*(?:\s-(?:[A-Za-z]*[rf][A-Za-z]*|r|f)|\s+--(?:recursive|force|no-preserve-root)))[^\n]*", scan_line, re.IGNORECASE):
            matched_destructive.add("rm -rf")
        if re.search(r"\btruncate\b", scan_line):
            matched_destructive.add("truncate")
        if "dd if=" in scan_line or re.search(r"\bdd\s+if=", scan_line):
            matched_destructive.add("dd if=")
        if re.search(r"\b(mkfs|shred|wipefs)\b", scan_line):
            m = re.search(r"\b(mkfs|shred|wipefs)\b", scan_line)
            if m:
                matched_destructive.add(m.group(1))

        # Network utilities
        for net_cmd in ("curl", "wget", "nc", "ncat", "netcat", "socat"):
            if re.search(rf"\b{net_cmd}\b", scan_line):
                matched_network.add(net_cmd)

        # Credentials and secrets
        if "~/.ssh" in scan_line or re.search(r"~/\.ssh\b", scan_line):
            matched_credentials.add("~/.ssh")
        if re.search(r"\.env\b", scan_line):
            matched_credentials.add(".env")
        for cred in ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "/etc/shadow", "/etc/passwd"):
            if cred in scan_line:
                matched_credentials.add(cred)
        if re.search(r"\bAWS_SECRET_ACCESS_KEY\b", scan_line):
            matched_credentials.add("AWS_SECRET_ACCESS_KEY")

        # Autonomy escalation
        if re.search(r"\bnohup\b", scan_line):
            matched_autonomy.add("nohup")
        if re.search(r"\bkill\s+-9\b", scan_line):
            matched_autonomy.add("kill -9")
        if re.search(r"\b(disown|pkill|killall)\b", scan_line):
            m = re.search(r"\b(disown|pkill|killall)\b", scan_line)
            if m:
                matched_autonomy.add(m.group(1))
        if re.search(r"(?<!&)&(?!&|>)", scan_line):
            matched_autonomy.add("&")

    return {
        "has_destructive": bool(matched_destructive),
        "has_network": bool(matched_network),
        "has_credential_access": bool(matched_credentials),
        "has_autonomy_escalation": bool(matched_autonomy),
        "matched_destructive": sorted(matched_destructive),
        "matched_network": sorted(matched_network),
        "matched_credentials": sorted(matched_credentials),
        "matched_autonomy": sorted(matched_autonomy),
    }


# ============================================================================
# Feature Extraction
# ============================================================================

@dataclass
class SkillFeatures:
    skill_name: str
    skill_dir: str
    description: str
    tools: List[str]
    file_count: int
    total_bytes: int
    python_files_count: int
    shell_files_count: int
    python_analysis: CodeAnalysis
    shell_analysis: Dict[str, Any]
    vector: List[float]
    vector_hash: str


def extract_features(skill_dir: str) -> SkillFeatures:
    """Inspects SKILL.md and any Python/shell scripts in skill_dir.

    Computes asset metrics (file counts, total bytes).
    Computes continuous vector metrics [0.0 - 1.0] and canonical deterministic vector_hash.
    """
    path = Path(skill_dir).resolve()
    skill_name = path.name
    description = ""
    tools: List[str] = []

    # Parse SKILL.md if present
    skill_md = path / "SKILL.md"
    body_scan_text = ""
    if skill_md.is_file():
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(content)
            body_scan_text = body
            if "name" in fm and fm["name"]:
                skill_name = str(fm["name"])
            if "description" in fm and fm["description"]:
                description = str(fm["description"])
            if "tools" in fm and isinstance(fm["tools"], list):
                tools = [str(t) for t in fm["tools"]]
            if description:
                body_scan_text = f"{description}\n{body_scan_text}"
        except Exception:
            pass

    file_count = 0
    total_bytes = 0
    python_files_count = 0
    shell_files_count = 0

    all_imported: Set[str] = set()
    all_dangerous: Set[str] = set()
    all_env_lookups: Set[str] = set()
    all_fs_calls: Set[str] = set()
    all_syntax_errors: List[str] = []

    all_matched_destructive: Set[str] = set()
    all_matched_network: Set[str] = set()
    all_matched_credentials: Set[str] = set()
    all_matched_autonomy: Set[str] = set()

    if body_scan_text:
        body_scan = scan_shell_script(body_scan_text)
        all_matched_destructive.update(body_scan["matched_destructive"])
        all_matched_network.update(body_scan["matched_network"])
        all_matched_credentials.update(body_scan["matched_credentials"])
        all_matched_autonomy.update(body_scan["matched_autonomy"])

    # Discover and inspect files deterministically
    if path.is_dir():
        file_entries = sorted(path.rglob("*"))
        for entry in file_entries:
            if not entry.is_file():
                continue
            # Skip VCS and cache directories
            parts = entry.parts
            if any(p in (".git", "__pycache__", ".pytest_cache", ".venv", "node_modules") for p in parts):
                continue

            file_count += 1
            try:
                size = entry.stat().st_size
                total_bytes += size
            except OSError:
                size = 0

            # Scan Python files
            if entry.suffix == ".py":
                python_files_count += 1
                try:
                    code = entry.read_text(encoding="utf-8", errors="replace")
                    analysis = analyze_python_code(code)
                    all_imported.update(analysis.imported_modules)
                    all_dangerous.update(analysis.dangerous_calls)
                    all_env_lookups.update(analysis.env_lookups)
                    all_fs_calls.update(analysis.filesystem_calls)
                    all_syntax_errors.extend(analysis.syntax_errors)
                except Exception as e:
                    all_syntax_errors.append(f"ReadError: {e}")

            # Scan Shell files
            elif entry.suffix in (".sh", ".bash"):
                shell_files_count += 1
                try:
                    script = entry.read_text(encoding="utf-8", errors="replace")
                    s_scan = scan_shell_script(script)
                    all_matched_destructive.update(s_scan["matched_destructive"])
                    all_matched_network.update(s_scan["matched_network"])
                    all_matched_credentials.update(s_scan["matched_credentials"])
                    all_matched_autonomy.update(s_scan["matched_autonomy"])
                except Exception:
                    pass

    combined_python = CodeAnalysis(
        imported_modules=sorted(all_imported),
        dangerous_calls=sorted(all_dangerous),
        env_lookups=sorted(all_env_lookups),
        filesystem_calls=sorted(all_fs_calls),
        syntax_errors=sorted(all_syntax_errors),
    )

    combined_shell = {
        "has_destructive": bool(all_matched_destructive),
        "has_network": bool(all_matched_network),
        "has_credential_access": bool(all_matched_credentials),
        "has_autonomy_escalation": bool(all_matched_autonomy),
        "matched_destructive": sorted(all_matched_destructive),
        "matched_network": sorted(all_matched_network),
        "matched_credentials": sorted(all_matched_credentials),
        "matched_autonomy": sorted(all_matched_autonomy),
    }

    # Continuous vector metrics [0.0 - 1.0]
    # Dimension 1: Destructive signal
    dest_count = len(combined_shell["matched_destructive"]) + len(
        [c for c in combined_python.dangerous_calls if any(k in c for k in ("rmtree", "system", "remove", "unlink"))]
    )
    dim_destructive = min(1.0, dest_count * 0.4)

    # Dimension 2: External network signal
    net_modules = {"urllib", "urllib.request", "requests", "http.client", "socket", "aiohttp", "httpx"}
    net_count = len(combined_shell["matched_network"]) + len(
        [m for m in combined_python.imported_modules if any(n in m for n in net_modules)]
    )
    dim_network = min(1.0, net_count * 0.35)

    # Dimension 3: Credential / sensitive env signal
    sensitive_env_count = len([
        v for v in combined_python.env_lookups
        if v not in BENIGN_ENV_NAMES and any(re.search(pat, v, re.IGNORECASE) for pat in SENSITIVE_ENV_PATTERNS)
    ])
    cred_count = len(combined_shell["matched_credentials"]) + sensitive_env_count
    dim_credential = min(1.0, cred_count * 0.35)

    # Dimension 4: Autonomy escalation signal
    auton_count = len(combined_shell["matched_autonomy"]) + len(
        [c for c in combined_python.dangerous_calls if "Popen" in c]
    )
    dim_autonomy = min(1.0, auton_count * 0.4)

    # Dimension 5: General python intensity
    py_activity = len(combined_python.dangerous_calls) + len(combined_python.filesystem_calls) + len(combined_python.env_lookups)
    dim_py_intensity = min(1.0, py_activity / 10.0)

    # Dimension 6: File count scale (log normalized)
    dim_file_scale = min(1.0, math.log1p(file_count) / 10.0)

    # Dimension 7: Byte count scale (log normalized)
    dim_byte_scale = min(1.0, math.log1p(total_bytes) / 20.0)

    # Dimension 8: Tool richness
    dim_tool_richness = min(1.0, len(tools) / 10.0)

    vector = [
        round(dim_destructive, 6),
        round(dim_network, 6),
        round(dim_credential, 6),
        round(dim_autonomy, 6),
        round(dim_py_intensity, 6),
        round(dim_file_scale, 6),
        round(dim_byte_scale, 6),
        round(dim_tool_richness, 6),
    ]

    # Canonical deterministic vector hash: sha256:<64-char-hex>
    canonical_data = {
        "skill_name": skill_name,
        "tools": sorted(tools),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "vector": vector,
    }
    canonical_bytes = json.dumps(canonical_data, sort_keys=True).encode("utf-8")
    vector_hash = f"sha256:{hashlib.sha256(canonical_bytes).hexdigest()}"

    return SkillFeatures(
        skill_name=skill_name,
        skill_dir=str(path),
        description=description,
        tools=tools,
        file_count=file_count,
        total_bytes=total_bytes,
        python_files_count=python_files_count,
        shell_files_count=shell_files_count,
        python_analysis=combined_python,
        shell_analysis=combined_shell,
        vector=vector,
        vector_hash=vector_hash,
    )


# ============================================================================
# Multi-Factor Risk Profiling
# ============================================================================

@dataclass
class RiskFactor:
    name: str
    weight: float
    score: float
    findings: List[str] = field(default_factory=list)


@dataclass
class RiskReport:
    verdict: str  # ALLOW, WARN, BLOCK
    overall_score: float
    factors: Dict[str, RiskFactor]
    redlines_triggered: List[str]


def profile_risk(features: SkillFeatures, policy: Optional[Dict[str, Any]] = None) -> RiskReport:
    """Calculates 4 orthogonal risk factors:

    - destructive_ops (weight 0.35)
    - external_network (weight 0.25)
    - credential_exposure (weight 0.25)
    - autonomy_escalation (weight 0.15)
    Triggers redlines on critical threats (rm -rf /, eval, raw exfiltration).
    Produces verdict based on an explicit threshold, which keeps exit policy and verdict semantics aligned.
    """
    threshold = float((policy or {}).get("risk_threshold", 0.70))
    redlines: List[str] = []

    # 1. Inspect Python & Shell for Redlines
    py = features.python_analysis
    sh = features.shell_analysis

    # Redline: eval or exec in Python code
    for d in py.dangerous_calls:
        if d in ("eval", "exec") or d.endswith(".eval") or d.endswith(".exec"):
            redlines.append(f"Dynamic code evaluation detected ({d})")

    # Redline: rm -rf / or shutil.rmtree('/')
    # Check shell files and Python files for root filesystem removal
    path = Path(features.skill_dir)
    if path.is_dir():
        for f in path.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix in (".py", ".sh", ".bash"):
                try:
                    text_content = f.read_text(encoding="utf-8", errors="replace")
                    # Check rm -rf /
                    if re.search(r"rm\s+-[a-zA-Z]*[rf][a-zA-Z]*\s+/\s*(?:$|[;|&])", text_content) or "rm -rf /" in text_content:
                        redlines.append("Destructive removal of root filesystem (rm -rf /)")
                    if "shutil.rmtree('/')" in text_content or 'shutil.rmtree("/")' in text_content:
                        redlines.append("Destructive removal of root directory via shutil.rmtree('/')")
                    # Raw exfiltration: credential piped or sent directly to network utility
                    if re.search(r"cat\s+~?/\.ssh[^\n|;&]*\|\s*(?:nc|netcat|ncat|curl|wget|socat)", text_content):
                        redlines.append("Raw credential exfiltration via network utility pipe")
                except Exception:
                    pass

    # Factor 1: Destructive operations (weight 0.35)
    dest_findings: List[str] = []
    for d in py.dangerous_calls:
        if any(k in d for k in ("rmtree", "system", "remove", "unlink")):
            dest_findings.append(f"Python destructive/system call: {d}")
    for d in sh["matched_destructive"]:
        dest_findings.append(f"Shell destructive command: {d}")

    if any("rm -rf /" in r or "shutil.rmtree('/')" in r for r in redlines):
        dest_score = 1.0
    elif dest_findings:
        dest_score = min(1.0, len(dest_findings) * 0.4)
    else:
        dest_score = 0.0

    # Factor 2: External network (weight 0.25)
    net_findings: List[str] = []
    net_modules = {"urllib", "urllib.request", "requests", "http.client", "socket", "aiohttp", "httpx"}
    for m in py.imported_modules:
        if any(nm in m for nm in net_modules):
            net_findings.append(f"Python network module import: {m}")
    for n in sh["matched_network"]:
        net_findings.append(f"Shell network utility: {n}")

    if net_findings:
        # Base network presence: 0.5, scaled with findings
        net_score = min(1.0, 0.3 + len(net_findings) * 0.2)
    else:
        net_score = 0.0

    # Factor 3: Credential exposure (weight 0.25)
    cred_findings: List[str] = []
    for v in py.env_lookups:
        if v not in BENIGN_ENV_NAMES and any(re.search(pat, v, re.IGNORECASE) for pat in SENSITIVE_ENV_PATTERNS):
            cred_findings.append(f"Sensitive env lookup: {v}")
    for c in sh["matched_credentials"]:
        cred_findings.append(f"Shell credential/secret access: {c}")

    if any("exfiltration" in r for r in redlines):
        cred_score = 1.0
    elif cred_findings:
        cred_score = min(1.0, 0.3 + len(cred_findings) * 0.25)
    else:
        cred_score = 0.0

    # Factor 4: Autonomy escalation (weight 0.15)
    auton_findings: List[str] = []
    for a in sh["matched_autonomy"]:
        auton_findings.append(f"Shell autonomy command: {a}")
    for d in py.dangerous_calls:
        if "Popen" in d:
            auton_findings.append(f"Subprocess background process call: {d}")

    if auton_findings:
        auton_score = min(1.0, len(auton_findings) * 0.35)
    else:
        auton_score = 0.0

    # Weights
    w_dest = 0.35
    w_net = 0.25
    w_cred = 0.25
    w_auton = 0.15

    # Check policy overrides if supplied
    if policy:
        weights = policy.get("weights", {})
        w_dest = weights.get("destructive_ops", w_dest)
        w_net = weights.get("external_network", w_net)
        w_cred = weights.get("credential_exposure", w_cred)
        w_auton = weights.get("autonomy_escalation", w_auton)

    factors = {
        "destructive_ops": RiskFactor(
            name="destructive_ops",
            weight=w_dest,
            score=round(dest_score, 4),
            findings=dest_findings,
        ),
        "external_network": RiskFactor(
            name="external_network",
            weight=w_net,
            score=round(net_score, 4),
            findings=net_findings,
        ),
        "credential_exposure": RiskFactor(
            name="credential_exposure",
            weight=w_cred,
            score=round(cred_score, 4),
            findings=cred_findings,
        ),
        "autonomy_escalation": RiskFactor(
            name="autonomy_escalation",
            weight=w_auton,
            score=round(auton_score, 4),
            findings=auton_findings,
        ),
    }

    weighted_score = sum(f.weight * f.score for f in factors.values())
    unique_redlines = sorted(list(set(redlines)))

    if unique_redlines:
        verdict = "BLOCK"
        overall_score = max(weighted_score, max(0.70, threshold))
    elif weighted_score >= threshold:
        verdict = "BLOCK"
        overall_score = weighted_score
    elif weighted_score >= 0.30:
        verdict = "WARN"
        overall_score = weighted_score
    else:
        verdict = "ALLOW"
        overall_score = weighted_score

    return RiskReport(
        verdict=verdict,
        overall_score=round(overall_score, 4),
        factors=factors,
        redlines_triggered=unique_redlines,
    )


# ============================================================================
# Compatibility Evaluator
# ============================================================================

@dataclass
class CompatibilityReport:
    target_harness: str
    status: str  # "compatible" or "incompatible"
    missing_tools: List[str]
    declared_tools: List[str]
    supported_tools: List[str]


def evaluate_compatibility(features: SkillFeatures, target_harness: str = "pi") -> CompatibilityReport:
    """Evaluates declared skill tools against harness profiles (pi, claude, codex, generic)."""
    norm_harness = target_harness.lower().strip()
    profile = HARNESS_PROFILES.get(norm_harness, set())

    declared = features.tools
    missing = [t for t in declared if t not in profile]
    status = "compatible" if not missing else "incompatible"

    return CompatibilityReport(
        target_harness=norm_harness,
        status=status,
        missing_tools=sorted(missing),
        declared_tools=sorted(declared),
        supported_tools=sorted(profile),
    )


# ============================================================================
# E2E Skill Audit Analysis
# ============================================================================

@dataclass
class SkillAuditReport:
    schema_version: str
    skill_name: str
    skill_dir: str
    features: SkillFeatures
    risk: RiskReport
    compatibility: CompatibilityReport

    @property
    def vector_hash(self) -> str:
        return self.features.vector_hash if self.features else ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_name": self.skill_name,
            "skill_dir": self.skill_dir,
            "vector_hash": self.vector_hash,
            "features": {
                "file_count": self.features.file_count,
                "total_bytes": self.features.total_bytes,
                "tools": self.features.tools,
                "vector": self.features.vector,
                "vector_hash": self.features.vector_hash,
                "python_files_count": self.features.python_files_count,
                "shell_files_count": self.features.shell_files_count,
            },
            "risk": {
                "verdict": self.risk.verdict,
                "overall_score": self.risk.overall_score,
                "redlines_triggered": self.risk.redlines_triggered,
                "factors": {
                    k: {
                        "name": v.name,
                        "weight": v.weight,
                        "score": v.score,
                        "findings": v.findings,
                    }
                    for k, v in self.risk.factors.items()
                },
            },
            "compatibility": {
                "target_harness": self.compatibility.target_harness,
                "status": self.compatibility.status,
                "missing_tools": self.compatibility.missing_tools,
                "declared_tools": self.compatibility.declared_tools,
            },
        }


def analyze_skill(skill_dir: str, target_harness: str = "pi") -> SkillAuditReport:
    """Full skill audit: feature extraction, risk profiling, and compatibility check."""
    features = extract_features(skill_dir)
    risk = profile_risk(features)
    compat = evaluate_compatibility(features, target_harness=target_harness)
    return SkillAuditReport(
        schema_version=SCHEMA_VERSION,
        skill_name=features.skill_name,
        skill_dir=str(Path(skill_dir).resolve()),
        features=features,
        risk=risk,
        compatibility=compat,
    )


# ============================================================================
# CLI Entrypoint
# ============================================================================

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Skill Gate: static feature extraction and risk profiling for agent skills."
    )
    parser.add_argument("skill_path", help="Path to the skill directory")
    parser.add_argument("--json", action="store_true", help="Output audit report as JSON")
    parser.add_argument(
        "--check-compat",
        nargs="?",
        const="pi",
        default=None,
        help="Check compatibility against target harness (e.g. pi, claude, codex, generic; default: pi)",
    )
    parser.add_argument(
        "--risk-threshold",
        type=float,
        default=0.70,
        help="Maximum risk score threshold before blocking (default: 0.70)",
    )
    parser.add_argument("--output", type=str, default=None, help="Write output to file instead of stdout")

    args = parser.parse_args(argv)

    skill_path = Path(args.skill_path)
    if not skill_path.exists() or not skill_path.is_dir():
        sys.stderr.write(f"Error: Invalid skill directory path: {args.skill_path}\n")
        return 1

    skill_md = skill_path / "SKILL.md"
    if not skill_md.is_file():
        sys.stderr.write(f"Error: Missing SKILL.md in {args.skill_path}\n")
        return 1

    target_harness = args.check_compat if args.check_compat else "pi"
    try:
        audit = analyze_skill(str(skill_path), target_harness=target_harness)
        audit.risk = profile_risk(audit.features, policy={"risk_threshold": args.risk_threshold})
    except Exception as e:
        sys.stderr.write(f"Error analyzing skill: {e}\n")
        return 1

    if args.json:
        out_content = json.dumps(audit.to_dict(), indent=2)
    else:
        lines = [
            f"Skill Audit Report: {audit.skill_name}",
            f"  Directory:     {audit.skill_dir}",
            f"  Vector Hash:   {audit.vector_hash}",
            f"  Risk Verdict:  {audit.risk.verdict} (score: {audit.risk.overall_score:.4f})",
        ]
        if audit.risk.redlines_triggered:
            lines.append("  Redlines:")
            for r in audit.risk.redlines_triggered:
                lines.append(f"    - {r}")
        lines.append(f"  Compatibility: {audit.compatibility.status} (target: {audit.compatibility.target_harness})")
        if audit.compatibility.missing_tools:
            lines.append(f"  Missing Tools: {', '.join(audit.compatibility.missing_tools)}")
        out_content = "\n".join(lines)

    if args.output:
        try:
            Path(args.output).write_text(out_content, encoding="utf-8")
        except OSError as e:
            sys.stderr.write(f"Error writing output file {args.output}: {e}\n")
            return 1
    else:
        print(out_content)

    # Determine exit code:
    # 0 = pass/allow
    # 1 = invalid path or error
    # 2 = blocked by policy
    # 3 = incompatible
    if audit.risk.verdict == "BLOCK" or audit.risk.overall_score >= args.risk_threshold:
        return 2

    if args.check_compat is not None and audit.compatibility.status == "incompatible":
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
