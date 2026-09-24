"""Static lexical analysis for shell content."""

from typing import Any, Dict, Set
import re

# ============================================================================
# Shell Script Lexical Scanner
# ============================================================================

def _shell_scan_text(line: str) -> str:
    """Normalize shell text to reduce lexical false positives from URLs and inline comments."""
    cleaned = re.sub(r"https?://\S+", " ", line)
    cleaned = re.sub(r"#.*$", " ", cleaned)
    return cleaned


def _shell_has_background_operator(line: str) -> bool:
    """Detect command-backgrounding ampersands, excluding quoted text and redirections."""
    unquoted = re.sub(r'(?:"[^"]*"|\'[^\']*\'|`[^`]*`)', " ", line)
    unquoted = re.sub(r"#.*$", " ", unquoted)
    return bool(re.search(r"(?:^|[\s;|])&(?:\s|$|[;|])", unquoted))


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
    matched_root_destructive: Set[str] = set()

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
        if re.search(r"\brm\b[^\n]*(?:^|[\s])/(?:\s|$|[;&|])", scan_line):
            matched_root_destructive.add("rm -rf /")
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
        for cred in ("id_rsa", "id_ed25519", "id_ecdsa", "id_dsa", "/etc/shadow"):
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
        if "nohup" not in matched_autonomy and _shell_has_background_operator(line):
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
        "has_root_destructive": bool(matched_root_destructive),
        "matched_root_destructive": sorted(matched_root_destructive),
    }
