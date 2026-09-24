#!/usr/bin/env python3
"""Skill Gate public API and CLI compatibility facade."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Optional

from _common import SCHEMA_VERSION
from ast_analysis import CodeAnalysis, analyze_python_code
from audit import SkillAuditReport, analyze_skill
from compat import CompatibilityReport, HARNESS_PROFILES, evaluate_compatibility
from features import SkillFeatures, extract_features
from frontmatter import parse_frontmatter
from risk import RiskFactor, RiskReport, profile_risk
from shell_scan import scan_shell_script

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
        if audit.features.warnings:
            lines.append("  Warnings:")
            for warning in audit.features.warnings:
                lines.append(f"    - {warning}")
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
