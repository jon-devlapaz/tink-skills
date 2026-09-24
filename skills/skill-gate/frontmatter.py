"""Minimal frontmatter parsing for skill metadata."""

from typing import Any, Dict, List, Tuple

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
