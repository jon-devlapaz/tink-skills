"""Feature extraction across a skill directory."""

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Set

from _common import BENIGN_ENV_NAMES, SENSITIVE_ENV_PATTERNS
from ast_analysis import CodeAnalysis, analyze_python_code
from frontmatter import parse_frontmatter
from shell_scan import scan_shell_script

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
    warnings: List[str]
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
    warnings: List[str] = []

    # Parse SKILL.md if present
    skill_md = path / "SKILL.md"
    body_scan_text = ""
    if skill_md.is_file():
        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(content)
            if content.lstrip().startswith("---") and not re.search(r"(?m)^---\s*$", content.split("\n", 1)[-1]):
                warnings.append("Frontmatter appears to be unclosed or malformed")
            body_scan_text = body
            if "name" in fm and fm["name"]:
                skill_name = str(fm["name"])
            if "description" in fm and fm["description"]:
                description = str(fm["description"])
            if "tools" in fm and isinstance(fm["tools"], list):
                tools = [str(t) for t in fm["tools"]]
            if description:
                body_scan_text = f"{description}\n{body_scan_text}"
        except Exception as e:
            warnings.append(f"ReadError: {skill_md}: {e}")

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
    all_matched_root_destructive: Set[str] = set()

    if body_scan_text:
        body_scan = scan_shell_script(body_scan_text)
        all_matched_destructive.update(body_scan["matched_destructive"])
        all_matched_network.update(body_scan["matched_network"])
        all_matched_credentials.update(body_scan["matched_credentials"])
        all_matched_autonomy.update(body_scan["matched_autonomy"])
        all_matched_root_destructive.update(body_scan["matched_root_destructive"])

    file_hashes: Dict[str, str] = {}
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

            try:
                rel_path = entry.relative_to(path).as_posix()
                file_bytes = entry.read_bytes()
                file_hashes[rel_path] = hashlib.sha256(file_bytes).hexdigest()
            except OSError:
                pass

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
            else:
                try:
                    first_line = entry.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
                    shebang = first_line[0] if first_line else ""
                except OSError as e:
                    shebang = ""
                    warnings.append(f"ReadError: {entry}: {e}")
                shebang_parts = shebang[2:].strip().split()
                interpreter = ""
                if shebang_parts:
                    interpreter = Path(shebang_parts[0]).name
                    if interpreter == "env" and len(shebang_parts) > 1:
                        interpreter = next(
                            (part for part in shebang_parts[1:] if not part.startswith("-")),
                            "",
                        )
                        interpreter = Path(interpreter).name
                shell_shebang = interpreter in {"sh", "bash", "zsh", "fish", "dash", "ksh", "ash"}
                if entry.suffix not in (".sh", ".bash") and not shell_shebang:
                    continue
                shell_files_count += 1
                try:
                    script = entry.read_text(encoding="utf-8", errors="replace")
                    s_scan = scan_shell_script(script)
                    all_matched_destructive.update(s_scan["matched_destructive"])
                    all_matched_network.update(s_scan["matched_network"])
                    all_matched_credentials.update(s_scan["matched_credentials"])
                    all_matched_autonomy.update(s_scan["matched_autonomy"])
                    all_matched_root_destructive.update(s_scan["matched_root_destructive"])
                except Exception as e:
                    warnings.append(f"ReadError: {entry}: {e}")

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
        "has_root_destructive": bool(all_matched_root_destructive),
        "matched_root_destructive": sorted(all_matched_root_destructive),
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
    py_activity = len(combined_python.filesystem_calls) + len(combined_python.env_lookups)
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
        "file_hashes": {k: file_hashes[k] for k in sorted(file_hashes)},
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
        warnings=sorted(warnings),
        vector=vector,
        vector_hash=vector_hash,
    )
