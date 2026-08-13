#!/usr/bin/env python3
"""Audit one local skill-evaluation suite without starting model trials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval_spec import load_suite


def _error_code(message: str) -> str:
    rules = (
        ("counter_reference is required", "missing_grader_contrast"),
        ("grader contrast", "non_discriminating_grader_contrast"),
        ("counter_reference", "invalid_grader_contrast"),
        ("artifact_sha256 does not match artifact", "provenance_hash_mismatch"),
        ("case_sha256 does not match eval case", "provenance_case_mismatch"),
        ("suite_sha256 does not match eval suite", "provenance_suite_mismatch"),
        ("should_trigger requires", "routing_loading_policy_conflict"),
        ("should_not_trigger requires", "routing_loading_policy_conflict"),
        ("ambiguous routing must declare", "routing_loading_policy_conflict"),
        ("does not cover every eval case", "provenance_coverage_mismatch"),
        ("distribution_policy", "invalid_legacy_policy"),
        ("provenance_manifest", "invalid_provenance_manifest"),
    )
    for needle, code in rules:
        if needle in message:
            return code
    return "invalid_eval_suite"


def audit(skill_path: Path, evals_path: Path | None = None) -> dict:
    try:
        suite = load_suite(skill_path, evals_path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        message = str(exc)
        return {
            "valid": False,
            "errors": [_error_code(message)],
            "details": [message],
        }
    routing_classes = sorted(
        {
            case["routing_class"]
            for case in suite["evals"]
            if case.get("routing_class")
        }
    )
    discrimination = {
        "claim": suite["grader_discrimination"],
        "contrast_case_count": sum(
            suite["grader_discrimination"] == "case_contrast"
            and case.get("counter_reference") is not None
            and case["grader_discrimination"][
                "response_sensitive_grader_count"
            ]
            > 0
            for case in suite["evals"]
        ),
        "response_sensitive_grader_count": sum(
            case["grader_discrimination"]["response_sensitive_grader_count"]
            for case in suite["evals"]
        ),
        "deterministic_graders_checked": sum(
            case["grader_discrimination"]["deterministic_graders_checked"]
            for case in suite["evals"]
        ),
        "model_graders_pending_runtime": sum(
            case["grader_discrimination"]["model_graders_pending_runtime"]
            for case in suite["evals"]
        ),
    }
    return {
        "valid": True,
        "errors": [],
        "schema_version": suite["schema_version"],
        "skill_name": suite["skill_name"],
        "suite_type": suite["suite_type"],
        "dataset_origin": suite["dataset_origin"],
        "activation_mode": suite["activation_mode"],
        "case_count": len(suite["evals"]),
        "routing_classes": routing_classes,
        "grader_discrimination": discrimination,
        "provenance_case_count": len(suite.get("provenance_records", {})),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate a local eval suite, its routing, and its provenance."
    )
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--evals-path", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)
    report = audit(args.skill_path, args.evals_path)
    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
