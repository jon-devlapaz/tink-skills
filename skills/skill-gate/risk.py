"""Risk scoring for extracted skill features."""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from _common import BENIGN_ENV_NAMES, SENSITIVE_ENV_PATTERNS
from features import SkillFeatures

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
        if d == "rm -rf /":
            redlines.append("Destructive removal of root filesystem (rm -rf /)")

    # Redline: rm -rf / or shutil.rmtree('/')
    path = Path(features.skill_dir)
    if path.is_dir():
        for f in path.rglob("*"):
            if not f.is_file():
                continue
            if f.suffix == ".py":
                try:
                    text_content = f.read_text(encoding="utf-8", errors="replace")
                    if "shutil.rmtree('/')" in text_content or 'shutil.rmtree("/")' in text_content:
                        redlines.append("Destructive removal of root directory via shutil.rmtree('/')")
                    # Raw exfiltration: credential piped or sent directly to network utility
                    if re.search(r"cat\s+~?/\.ssh[^\n|;&]*\|\s*(?:nc|netcat|ncat|curl|wget|socat)", text_content):
                        redlines.append("Raw credential exfiltration via network utility pipe")
                except Exception:
                    pass
    if sh.get("has_root_destructive"):
        redlines.append("Destructive removal of root filesystem (rm -rf /)")

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
