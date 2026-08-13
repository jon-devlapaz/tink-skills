#!/usr/bin/env python3
"""Run a pinned, no-tools harness model as a rubric grader."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from runtime_adapters import build_judge_invocation, trace_metadata
from runtime_attestation import require_judge_runtime_attestation
from process_control import run_captured


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_grade(response: str) -> dict:
    candidates = [response.strip()]
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.S)
    candidates = fenced + candidates
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(value, dict)
            and type(value.get("passed")) is bool
            and isinstance(value.get("reason"), str)
            and value["reason"].strip()
        ):
            return {"passed": value["passed"], "reason": value["reason"].strip()}
    raise ValueError("judge did not return {passed: boolean, reason: string}")


def run_model_grade(
    *,
    harness: str = "pi",
    executable: str,
    model: str,
    task_prompt: str,
    rubric: str,
    candidate_response: str,
    reference_response: str,
    trace_path: Path,
    timeout_seconds: int,
    herdr_run: Any | None = None,
    display_title: str = "Judge",
) -> tuple[dict, dict]:
    judge_prompt = f"""You are grading one agent response.

TASK:
{task_prompt}

RUBRIC:
{rubric}

KNOWN-GOOD REFERENCE:
{reference_response}

CANDIDATE:
{candidate_response}

Judge the candidate against the task and rubric, not by exact wording or
similarity to the reference. The candidate passes only if it satisfies every
rubric requirement. Return JSON only:
{{"passed": true, "reason": "specific evidence"}}
"""
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    invocation = build_judge_invocation(
        harness=harness,
        executable=executable,
        model=model,
        prompt=judge_prompt,
        run_dir=trace_path.parent,
    )
    stderr_path = trace_path.parent / f"{trace_path.stem}.stderr.txt"
    if herdr_run is None:
        completed, timed_out = run_captured(
            invocation.command,
            env=invocation.env,
            timeout_seconds=timeout_seconds,
        )
        trace_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
    else:
        completed, timed_out = herdr_run.run_captured(
            invocation.command,
            cwd=None,
            env=invocation.env,
            timeout_seconds=timeout_seconds,
            pane_role="judge_results",
            title=display_title,
            trace_path=trace_path,
            stderr_path=stderr_path,
        )
    if timed_out:
        raise RuntimeError(
            f"judge timed out after {timeout_seconds} seconds; see {trace_path}"
        )
    if completed.returncode != 0:
        raise RuntimeError(
            f"judge exited {completed.returncode}; see {trace_path}"
        )
    metadata = trace_metadata(
        trace_path,
        "",
        harness=harness,
        requested_model=model,
        usage_path=(
            trace_path.parent / "usage.json" if harness == "hermes" else None
        ),
        codex_home=(
            Path(invocation.env["CODEX_HOME"])
            if harness == "codex"
            else None
        ),
    )
    require_judge_runtime_attestation(
        metadata,
        harness=harness,
        requested_model=model,
        trace_path=trace_path,
    )
    attestation_trace = metadata.get("attestation_trace_path")
    grade = _parse_grade(str(metadata.get("final_response", "")))
    evidence = {
        "passed": grade["passed"],
        "evidence": grade["reason"],
    }
    provenance = {
        "requested_model": model,
        "actual_model": metadata["actual_model"],
        "model_attested": metadata["model_attested"],
        "session_id": metadata["session_id"],
        "trace_path": str(trace_path),
        "trace_sha256": _sha256_file(trace_path),
        "attestation_trace_path": (
            str(attestation_trace) if attestation_trace else ""
        ),
        "attestation_trace_sha256": (
            _sha256_file(Path(attestation_trace))
            if attestation_trace
            else ""
        ),
        "total_tokens": metadata.get("total_tokens"),
        "cost": metadata.get("cost"),
    }
    return evidence, provenance
