"""Static Python AST analysis for skill code."""

from dataclasses import dataclass, field
from typing import List, Set
import ast

from shell_scan import scan_shell_script

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
    if isinstance(curr, ast.Call):
        called = _get_call_name(curr.func)
        if called:
            parts.append(called)
        return ".".join(reversed(parts))
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
        "eval", "exec", "os.popen", "rmtree", "system", "os.remove",
        "os.unlink", "os.rename", "os.replace", "shutil.copy",
        "shutil.copy2", "shutil.copyfile", "shutil.move"
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

                if call_name in {
                    "os.system", "os.popen", "subprocess.run", "subprocess.Popen",
                    "subprocess.call", "subprocess.check_call", "subprocess.check_output",
                }:
                    literal_parts: List[str] = []
                    for arg in node.args:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            literal_parts.append(arg.value)
                        elif isinstance(arg, (ast.List, ast.Tuple)):
                            literal_parts.extend(
                                str(item.value)
                                for item in arg.elts
                                if isinstance(item, ast.Constant) and isinstance(item.value, str)
                            )
                    if scan_shell_script(" ".join(literal_parts)).get("has_root_destructive"):
                        dangerous.add("rm -rf /")

                shell_true = any(
                    kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in node.keywords
                )
                if shell_true and (call_name.startswith("subprocess.") or call_name in {"subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output"}):
                    dangerous.add(f"{call_name}:shell=True")

                # Dynamic dispatch/tripwire: __import__(...) and getattr(...)
                if call_name in ("__import__", "getattr") or call_name.endswith(".__import__") or call_name.endswith(".getattr"):
                    dangerous.add(call_name)

                # Environment variable lookups via calls: os.environ.get(...), os.getenv(...)
                if call_name in ("os.environ.get", "os.getenv", "environ.get", "getenv"):
                    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                        env_lookups.add(node.args[0].value)

                # Filesystem write operations
                if call_name.endswith(".open"):
                    is_write = False
                    if node.args and isinstance(node.args[0], ast.Constant):
                        mode = str(node.args[0].value)
                        if any(m in mode for m in ("w", "a", "x", "+")):
                            is_write = True
                    elif node.args:
                        fs_calls.add("open:unknown_mode")
                    for kw in node.keywords:
                        if kw.arg == "mode":
                            if isinstance(kw.value, ast.Constant):
                                mode = str(kw.value.value)
                                if any(m in mode for m in ("w", "a", "x", "+")):
                                    is_write = True
                            else:
                                fs_calls.add("open:unknown_mode")
                    if is_write:
                        fs_calls.add("open:write")
                elif call_name == "open":
                    is_write = False
                    if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                        mode = str(node.args[1].value)
                        if any(m in mode for m in ("w", "a", "x", "+")):
                            is_write = True
                    elif len(node.args) >= 2:
                        fs_calls.add("open:unknown_mode")
                    for kw in node.keywords:
                        if kw.arg == "mode":
                            if isinstance(kw.value, ast.Constant):
                                mode = str(kw.value.value)
                                if any(m in mode for m in ("w", "a", "x", "+")):
                                    is_write = True
                            else:
                                fs_calls.add("open:unknown_mode")
                    if is_write:
                        fs_calls.add("open:write")
                elif call_name.endswith(".write_text") or call_name == "write_text":
                    fs_calls.add("Path.write_text")
                elif call_name.endswith(".write_bytes") or call_name == "write_bytes":
                    fs_calls.add("Path.write_bytes")
                elif (call_name.endswith(".write") or call_name == "write") and not call_name.startswith(("sys.", "StringIO.")):
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
