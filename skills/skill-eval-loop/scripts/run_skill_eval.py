#!/usr/bin/env python3
"""Run a paired control/treatment skill evaluation with a selected harness."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aggregate_benchmark import aggregate
from eval_runtime import (
    OBSERVERS,
    observer_plan,
    require_observer_environment,
    start_eval_run,
)
from eval_spec import (
    canonical_sha256,
    grade_case,
    harness_invocation_counts,
    load_suite,
    safe_relative_path,
)
from model_grader import run_model_grade
from runtime_adapters import (
    HARNESS_NAMES,
    build_invocation,
    resolve_harness,
    skill_payload_sha256,
    trace_metadata,
    validate_pinned_model,
)
from runtime_attestation import require_target_runtime_attestation
from workspace_paths import DEFAULT_EVAL_RUNS_ROOT, default_run_output


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _finish_observer(
    eval_run: Any,
    *,
    status: str,
    summary: str,
    artifact_path: Path,
) -> None:
    try:
        eval_run.finish(
            status=status,
            summary=summary,
            artifact_path=artifact_path,
        )
    except Exception as exc:
        print(f"WARNING: could not finalize run observer: {exc}", file=sys.stderr)


def condition_order(trial: int) -> tuple[str, str]:
    if trial < 1:
        raise ValueError("trial must be at least 1")
    if trial % 2:
        return ("without_skill", "with_skill")
    return ("with_skill", "without_skill")


def _observer_state(eval_run: Any) -> dict[str, str]:
    state = {"observer": str(eval_run.observer)}
    if eval_run.workspace_id:
        state["workspace_id"] = str(eval_run.workspace_id)
    if eval_run.workspace_label:
        state["workspace_label"] = str(eval_run.workspace_label)
    return state


def _prepare_workspace(
    suite_root: Path,
    case: dict,
    workspace: Path,
    *,
    reference: bool = False,
) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    container = case["reference"] if reference else case
    key = "workspace" if reference else "fixture"
    relative = container.get(key)
    if not relative:
        return
    source = safe_relative_path(suite_root, relative, f"{case['id']}.{key}")
    if not source.is_dir():
        raise FileNotFoundError(f"fixture directory not found: {source}")
    shutil.copytree(source, workspace, dirs_exist_ok=True)


def _model_graders(
    *,
    case: dict,
    response: str,
    trace_dir: Path,
    root: Path,
    harness: str,
    executable: str,
    judge_model: str | None,
    timeout_seconds: int,
    eval_run: Any,
    display_context: str,
) -> tuple[dict[str, dict], list[dict]]:
    graders = [
        grader for grader in case["graders"] if grader["type"] == "model_rubric"
    ]
    if graders and not judge_model:
        raise ValueError("model_rubric graders require --judge-model")
    external: dict[str, dict] = {}
    records: list[dict] = []
    for index, grader in enumerate(graders, start=1):
        trace_path = trace_dir / f"judge-{index:03d}.jsonl"
        grade, record = run_model_grade(
            harness=harness,
            executable=executable,
            model=str(judge_model),
            task_prompt=case["prompt"],
            rubric=grader["rubric"],
            candidate_response=response,
            reference_response=case["reference"].get("response", ""),
            trace_path=trace_path,
            timeout_seconds=timeout_seconds,
            herdr_run=eval_run,
            display_title=f"Judge · {display_context} · {grader['name']}",
        )
        record["grader_name"] = grader["name"]
        record["trace_path"] = str(trace_path.relative_to(root))
        if record.get("attestation_trace_path"):
            record["attestation_trace_path"] = str(
                Path(record["attestation_trace_path"]).relative_to(root)
            )
        external[grader["name"]] = grade
        records.append(record)
    return external, records


def _grade_counter_reference(
    *,
    case: dict,
    suite_root: Path,
    output_dir: Path,
    harness: str,
    executable: str,
    judge_model: str | None,
    judge_timeout_seconds: int,
    eval_run: Any,
) -> dict | None:
    """Grade a deliberately wrong answer, when the case declares one.

    The reference check above proves the graders accept a correct answer. It
    cannot show they reject an incorrect one, and graders that accept everything
    report a confident verdict for both conditions of the paired run.

    Returns the grading, or None when the case declares no counter-reference.
    """
    counter_reference = case.get("counter_reference")
    if counter_reference is None:
        return None
    response = counter_reference["response"]
    with tempfile.TemporaryDirectory(prefix="skill-eval-counter-") as temp:
        workspace = Path(temp)
        _prepare_workspace(suite_root, case, workspace, reference=True)
        external, judge_records = _model_graders(
            case=case,
            response=response,
            trace_dir=output_dir / "counter-reference-judges" / case["id"],
            root=output_dir,
            harness=harness,
            executable=executable,
            judge_model=judge_model,
            timeout_seconds=judge_timeout_seconds,
            eval_run=eval_run,
            display_context=f"counter-reference · {case['id']}",
        )
        return {
            "grading": grade_case(
                workspace=workspace,
                response=response,
                graders=case["graders"],
                external_grades=external,
            ),
            "judge_records": judge_records,
        }


def _validate_references(
    *,
    suite_root: Path,
    suite: dict,
    output_dir: Path,
    harness: str,
    executable: str,
    judge_model: str | None,
    judge_timeout_seconds: int,
    eval_run: Any,
) -> list[dict]:
    records: list[dict] = []
    for case in suite["evals"]:
        with tempfile.TemporaryDirectory(prefix="skill-eval-reference-") as temp:
            workspace = Path(temp)
            _prepare_workspace(suite_root, case, workspace, reference=True)
            external, judge_records = _model_graders(
                case=case,
                response=case["reference"].get("response", ""),
                trace_dir=output_dir / "reference-judges" / case["id"],
                root=output_dir,
                harness=harness,
                executable=executable,
                judge_model=judge_model,
                timeout_seconds=judge_timeout_seconds,
                eval_run=eval_run,
                display_context=f"reference · {case['id']}",
            )
            grading = grade_case(
                workspace=workspace,
                response=case["reference"].get("response", ""),
                graders=case["graders"],
                external_grades=external,
            )
        if grading["summary"]["failed"]:
            raise ValueError(f"reference solution failed graders for case {case['id']}")
        counter_grading = _grade_counter_reference(
            case=case,
            suite_root=suite_root,
            output_dir=output_dir,
            harness=harness,
            executable=executable,
            judge_model=judge_model,
            judge_timeout_seconds=judge_timeout_seconds,
            eval_run=eval_run,
        )
        if (
            counter_grading is not None
            and not counter_grading["grading"]["summary"]["failed"]
        ):
            raise ValueError(
                f"counter-reference passed graders for case {case['id']}; "
                "the graders do not separate a correct answer from a wrong one"
            )
        record = {
            "case_id": case["id"],
            "valid": True,
            "grading": grading,
            "judge_records": judge_records,
        }
        if counter_grading is not None:
            record["counter_reference"] = counter_grading
        records.append(record)
    return records


def _retain_provenance(output_dir: Path, suite: dict) -> tuple[str | None, str | None]:
    records = suite.get("provenance_records") or {}
    if not records:
        return None, None
    suite_root = Path(suite["suite_root"])
    retained: list[dict] = []
    for case_id, record in sorted(records.items()):
        source = safe_relative_path(
            suite_root,
            record["artifact"],
            f"provenance.{case_id}.artifact",
        )
        destination = output_dir / "provenance" / f"{case_id}{source.suffix or '.json'}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        retained.append(
            {
                **record,
                "retained_artifact_path": str(destination.relative_to(output_dir)),
                "retained_artifact_sha256": _sha256_file(destination),
            }
        )
    snapshot = {
        "schema_version": 1,
        "source_manifest_sha256": suite.get("provenance_sha256"),
        "cases": retained,
    }
    path = output_dir / "provenance_snapshot.json"
    _write_json(path, snapshot)
    return str(path.relative_to(output_dir)), _sha256_file(path)


def _run_condition(
    *,
    root: Path,
    skill_path: Path,
    case: dict,
    suite_root: Path,
    trial: int,
    condition: str,
    harness: str,
    executable: str,
    model: str,
    timeout_seconds: int,
    judge_model: str | None,
    judge_timeout_seconds: int,
    eval_run: Any,
) -> dict:
    condition_dir = root / f"eval-{case['id']}" / f"trial-{trial:03d}" / condition
    workspace = condition_dir / "workspace"
    _prepare_workspace(suite_root, case, workspace)
    invocation = build_invocation(
        harness=harness,
        executable=executable,
        condition=condition,
        condition_dir=condition_dir,
        skill_path=skill_path,
        prompt=case["prompt"],
        model=model,
        tool_profile=case["_tool_profile"],
        activation_mode=case["_activation_mode"],
    )
    outputs = condition_dir / "outputs"
    outputs.mkdir(parents=True)
    trace_path = outputs / "trace.jsonl"
    stderr_path = outputs / "stderr.txt"
    response_path = outputs / "response.md"
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    pane_role = "control" if condition == "without_skill" else "with_skill"
    display_condition = "control" if condition == "without_skill" else "with-skill"
    completed, timed_out = eval_run.run_captured(
        invocation.command,
        cwd=workspace,
        env=invocation.env,
        timeout_seconds=timeout_seconds,
        pane_role=pane_role,
        title=f"{display_condition} · {case['id']} · trial {trial}",
        trace_path=trace_path,
        stderr_path=stderr_path,
    )
    duration = time.monotonic() - started
    metadata = trace_metadata(
        trace_path,
        skill_path.name,
        invocation.installed_skill_path,
        harness=harness,
        requested_model=model,
        usage_path=(outputs / "usage.json" if harness == "hermes" else None),
        codex_home=(
            Path(invocation.env["CODEX_HOME"])
            if harness == "codex"
            else None
        ),
    )
    require_target_runtime_attestation(
        metadata,
        harness=harness,
        requested_model=model,
        condition=condition,
        activation_mode=case["_activation_mode"],
        skill_name=skill_path.name,
        trace_path=trace_path,
    )
    if timed_out or completed.returncode != 0:
        status = "timed out" if timed_out else f"exited {completed.returncode}"
        raise RuntimeError(
            f"target invocation failed ({status}); retained trace at {trace_path}"
        )
    attestation_trace = metadata.get("attestation_trace_path")
    response = str(metadata.get("final_response", ""))
    response_path.write_text(response + ("\n" if response else ""), encoding="utf-8")
    external, judge_records = _model_graders(
        case=case,
        response=response,
        trace_dir=outputs / "judges",
        root=root,
        harness=harness,
        executable=executable,
        judge_model=judge_model,
        timeout_seconds=judge_timeout_seconds,
        eval_run=eval_run,
        display_context=f"{display_condition} · {case['id']} · trial {trial}",
    )
    grading = grade_case(
        workspace=workspace,
        response=response,
        graders=case["graders"],
        external_grades=external,
    )
    grading_path = condition_dir / "grading.json"
    _write_json(grading_path, grading)
    return {
        "case_id": case["id"],
        "trial": trial,
        "condition": condition,
        "started_at": started_at,
        "duration_seconds": round(duration, 6),
        "exit_code": completed.returncode,
        "timed_out": timed_out,
        "requested_model": model,
        "actual_model": metadata["actual_model"],
        "model_attested": metadata["model_attested"],
        "session_id": metadata["session_id"],
        "input_tokens": metadata.get("input_tokens"),
        "output_tokens": metadata.get("output_tokens"),
        "total_tokens": metadata.get("total_tokens"),
        "cost": metadata.get("cost"),
        "available_skills": invocation.available_skills,
        "skill_available": condition == "with_skill",
        "skill_activation": invocation.skill_activation,
        "requested_tools": invocation.exposed_tools,
        "tool_enforcement": invocation.tool_enforcement,
        "installed_skill_path": (
            str(invocation.installed_skill_path.relative_to(root))
            if invocation.installed_skill_path
            else ""
        ),
        "skill_injection_attested": metadata["skill_injection_attested"],
        "skill_explicitly_accessed": metadata["skill_explicitly_accessed"],
        "expected_skill_loading": (
            case["expected_skill_loading"] if condition == "with_skill" else "forbidden"
        ),
        "judge_records": judge_records,
        "trace_path": str(trace_path.relative_to(root)),
        "trace_sha256": _sha256_file(trace_path),
        "attestation_trace_path": (
            str(Path(attestation_trace).relative_to(root))
            if attestation_trace
            else ""
        ),
        "attestation_trace_sha256": (
            _sha256_file(Path(attestation_trace))
            if attestation_trace
            else ""
        ),
        "response_path": str(response_path.relative_to(root)),
        "response_sha256": _sha256_file(response_path),
        "grading_path": str(grading_path.relative_to(root)),
        "grading_sha256": _sha256_file(grading_path),
    }


def _assert_external_output(output_dir: Path, skill_path: Path) -> None:
    skills_root = DEFAULT_EVAL_RUNS_ROOT.parent / "skills"
    resolved_output = output_dir.resolve()
    if resolved_output.is_relative_to(skills_root.resolve()):
        raise ValueError(f"evaluation output cannot live inside {skills_root}")
    if resolved_output.is_relative_to(skill_path.resolve()):
        raise ValueError(
            f"evaluation output cannot live inside evaluated skill {skill_path}"
        )


def _assert_fixture_isolation(suite: dict, skill_name: str) -> None:
    suite_root = Path(suite["suite_root"])
    native_roots = (Path(".agents/skills"), Path(".claude/skills"))
    for case in suite["evals"]:
        relative = case.get("fixture")
        if not relative:
            continue
        fixture = safe_relative_path(
            suite_root,
            relative,
            f"{case['id']}.fixture",
        )
        for native_root in native_roots:
            contaminated = fixture / native_root / skill_name
            if contaminated.exists() or contaminated.is_symlink():
                raise ValueError(
                    f"control fixture for {case['id']} contains target skill at "
                    f"{contaminated}"
                )


def plan_run(
    *,
    skill_path: Path,
    output_dir: Path,
    model: str,
    trials: int,
    evals_path: Path | None = None,
    harness: str = "pi",
    harness_bin: str | None = None,
    pi_bin: str | None = None,
    judge_model: str | None = None,
    observer: str = "headless",
) -> dict:
    if trials < 1:
        raise ValueError("trials must be at least 1")
    validate_pinned_model(model)
    if judge_model:
        validate_pinned_model(judge_model)
    skill_path = skill_path.resolve()
    if not (skill_path / "SKILL.md").is_file():
        raise FileNotFoundError(f"skill has no SKILL.md: {skill_path}")
    suite = load_suite(skill_path, evals_path)
    if harness not in HARNESS_NAMES:
        raise ValueError(f"harness must be one of {list(HARNESS_NAMES)}")
    _assert_fixture_isolation(suite, skill_path.name)
    if pi_bin and harness != "pi":
        raise ValueError("--pi-bin can only be used with --harness pi")
    if observer not in OBSERVERS:
        raise ValueError(f"observer must be one of {sorted(OBSERVERS)}")
    _assert_external_output(output_dir, skill_path)
    model_rubric_counts = [
        sum(grader["type"] == "model_rubric" for grader in case["graders"])
        for case in suite["evals"]
    ]
    if any(model_rubric_counts) and not judge_model:
        raise ValueError("model_rubric graders require --judge-model")
    executable, version = resolve_harness(
        harness,
        harness_bin or pi_bin,
    )
    invocation_counts = harness_invocation_counts(
        trials=trials,
        model_rubric_counts=model_rubric_counts,
        counter_reference_declared=[
            case.get("counter_reference") is not None for case in suite["evals"]
        ],
    )
    return {
        "skill_path": str(skill_path),
        "evals_path": suite["source_path"],
        "output_dir": str(output_dir.resolve()),
        "harness": harness,
        "harness_path": executable,
        "harness_version": version,
        "model": model,
        "judge_model": judge_model,
        "activation_mode": suite["activation_mode"],
        "trials_per_case": trials,
        "case_count": len(suite["evals"]),
        "pair_count": len(suite["evals"]) * trials,
        "harness_invocations": invocation_counts,
        "provider_model_calls": "unknown",
        "execution_order": {
            "policy": "counterbalanced_by_trial",
            "odd_trials": list(condition_order(1)),
            "even_trials": list(condition_order(2)),
        },
        "observer": observer_plan(observer, skill_path.name, output_dir),
    }


def run_suite(
    *,
    skill_path: Path,
    output_dir: Path,
    model: str,
    trials: int = 3,
    evals_path: Path | None = None,
    harness: str = "pi",
    harness_bin: str | None = None,
    pi_bin: str | None = None,
    timeout_seconds: int = 120,
    judge_model: str | None = None,
    judge_timeout_seconds: int = 120,
    observer: str = "headless",
) -> dict:
    require_observer_environment(observer)
    plan = plan_run(
        skill_path=skill_path,
        evals_path=evals_path,
        output_dir=output_dir,
        model=model,
        trials=trials,
        harness=harness,
        harness_bin=harness_bin,
        pi_bin=pi_bin,
        judge_model=judge_model,
        observer=observer,
    )
    output_dir = Path(plan["output_dir"])
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} already exists; choose a new output")
    skill_path = skill_path.resolve()
    suite = load_suite(skill_path, evals_path)
    suite_root = Path(suite["suite_root"])
    for case in suite["evals"]:
        case["_tool_profile"] = suite["tool_profile"]
        case["_activation_mode"] = suite["activation_mode"]

    output_dir.mkdir(parents=True)
    state_path = output_dir / "run_state.json"
    _write_json(
        state_path,
        {
            "status": "starting",
            "valid": False,
            "completed_conditions": 0,
        },
    )
    try:
        eval_run = start_eval_run(
            observer,
            skill_name=skill_path.name,
            output_dir=output_dir,
            cwd=Path.cwd(),
        )
    except Exception as exc:
        _write_json(
            state_path,
            {
                "status": "failed",
                "valid": False,
                "error": str(exc),
                "completed_conditions": 0,
            },
        )
        raise
    _write_json(
        state_path,
        {
            "status": "running",
            "valid": False,
            **_observer_state(eval_run),
            "completed_conditions": 0,
        },
    )
    completed_conditions = 0
    try:
        references = _validate_references(
            suite_root=suite_root,
            suite=suite,
            output_dir=output_dir,
            harness=harness,
            executable=plan["harness_path"],
            judge_model=judge_model,
            judge_timeout_seconds=judge_timeout_seconds,
            eval_run=eval_run,
        )
        provenance_path, provenance_sha256 = _retain_provenance(output_dir, suite)
        suite_snapshot = {
            "schema_version": suite["schema_version"],
            "skill_name": suite["skill_name"],
            "suite_type": suite["suite_type"],
            "dataset_origin": suite["dataset_origin"],
            "tool_profile": suite["tool_profile"],
            "activation_mode": suite["activation_mode"],
            "distribution_policy": suite.get("distribution_policy"),
            "source_sha256": _sha256_file(Path(suite["source_path"])),
            "cases": [
                {
                    "id": case["id"],
                    "behavior_class": case["behavior_class"],
                    "routing_class": case.get("routing_class"),
                    "expected_skill_loading": case["expected_skill_loading"],
                    "model_rubric_count": sum(
                        grader["type"] == "model_rubric"
                        for grader in case["graders"]
                    ),
                    "counter_reference_declared": (
                        case.get("counter_reference") is not None
                    ),
                    "prompt_sha256": canonical_sha256(case["prompt"]),
                    "graders_sha256": canonical_sha256(case["graders"]),
                }
                for case in suite["evals"]
            ],
        }
        suite_path = output_dir / "suite_snapshot.json"
        _write_json(suite_path, suite_snapshot)

        pairs = {
            (case["id"], trial): {
                "case_id": case["id"],
                "trial": trial,
                "conditions": {},
            }
            for case in suite["evals"]
            for trial in range(1, trials + 1)
        }
        execution_schedule: list[dict] = []
        for case in suite["evals"]:
            for trial in range(1, trials + 1):
                order = condition_order(trial)
                pairs[(case["id"], trial)]["execution_order"] = list(order)
                execution_schedule.append(
                    {
                        "case_id": case["id"],
                        "trial": trial,
                        "conditions": list(order),
                    }
                )
                for condition in order:
                    pairs[(case["id"], trial)]["conditions"][condition] = _run_condition(
                        root=output_dir,
                        skill_path=skill_path,
                        case=case,
                        suite_root=suite_root,
                        trial=trial,
                        condition=condition,
                        harness=harness,
                        executable=plan["harness_path"],
                        model=model,
                        timeout_seconds=timeout_seconds,
                        judge_model=judge_model,
                        judge_timeout_seconds=judge_timeout_seconds,
                        eval_run=eval_run,
                    )
                    completed_conditions += 1
                    _write_json(
                        state_path,
                        {
                            "status": "running",
                            "valid": False,
                            **_observer_state(eval_run),
                            "completed_conditions": completed_conditions,
                        },
                    )

        manifest = {
            "schema_version": 1,
            "target_skill_name": skill_path.name,
            "decision": (
                "Does autonomous access to the target skill improve task success?"
                if suite["activation_mode"] == "autonomous"
                else "Does forced loading of the target skill improve task success?"
            ),
            "condition_variable": (
                f"{harness} native skill availability versus isolated control"
                if suite["activation_mode"] == "autonomous"
                else f"{harness} explicit skill activation versus isolated control"
            ),
            "skill_sha256": skill_payload_sha256(skill_path),
            "suite_path": str(suite_path.relative_to(output_dir)),
            "suite_sha256": _sha256_file(suite_path),
            "provenance_path": provenance_path,
            "provenance_sha256": provenance_sha256,
            "requested_model": model,
            "judge_model": judge_model,
            "harness": harness,
            "harness_version": plan["harness_version"],
            **_observer_state(eval_run),
            "tool_profile": suite["tool_profile"],
            "activation_mode": suite["activation_mode"],
            "execution_order": "counterbalanced_by_trial",
            "execution_schedule": execution_schedule,
            "case_count": len(suite["evals"]),
            "trials_per_case": trials,
            "pair_count": len(pairs),
            "reference_validation": references,
            "trials": list(pairs.values()),
        }
        _write_json(output_dir / "run_manifest.json", manifest)
        report = aggregate(output_dir)
        _write_json(output_dir / "benchmark.json", report)
    except KeyboardInterrupt:
        _write_json(
            state_path,
            {
                "status": "cancelled",
                "valid": False,
                **_observer_state(eval_run),
                "completed_conditions": completed_conditions,
            },
        )
        _finish_observer(
            eval_run,
            status="cancelled",
            summary=f"Cancelled after {completed_conditions} completed conditions",
            artifact_path=output_dir,
        )
        raise
    except Exception as exc:
        _write_json(
            state_path,
            {
                "status": "failed",
                "valid": False,
                "error": str(exc),
                **_observer_state(eval_run),
                "completed_conditions": completed_conditions,
            },
        )
        _finish_observer(
            eval_run,
            status="failed",
            summary=str(exc),
            artifact_path=output_dir,
        )
        raise
    final_status = "completed" if report["valid"] else "invalid"
    _write_json(
        state_path,
        {
            "status": final_status,
            "valid": bool(report["valid"]),
            "verdict": report.get("verdict"),
            **_observer_state(eval_run),
            "completed_conditions": completed_conditions,
        },
    )
    _finish_observer(
        eval_run,
        status=final_status,
        summary=f"Verdict: {report.get('verdict')} · valid: {report['valid']}",
        artifact_path=output_dir,
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a paired harness evaluation with and without one skill."
    )
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--evals-path", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Defaults to .eval-runs/<skill-name>/<run-id>/.",
    )
    parser.add_argument("--model", required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--harness", required=True, choices=HARNESS_NAMES)
    parser.add_argument("--harness-bin")
    parser.add_argument("--pi-bin")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--judge-model")
    parser.add_argument("--judge-timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--observer",
        choices=sorted(OBSERVERS),
        default="headless",
        help="Run headlessly or mirror processes in a retained Herdr workspace.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print the run plan without creating files or calling a model.",
    )
    args = parser.parse_args(argv)
    output_dir = args.output_dir or default_run_output(args.skill_path.name)
    try:
        if args.dry_run:
            report = plan_run(
                skill_path=args.skill_path,
                evals_path=args.evals_path,
                output_dir=output_dir,
                model=args.model,
                trials=args.trials,
                harness=args.harness,
                harness_bin=args.harness_bin,
                pi_bin=args.pi_bin,
                judge_model=args.judge_model,
                observer=args.observer,
            )
        else:
            report = run_suite(
                skill_path=args.skill_path,
                evals_path=args.evals_path,
                output_dir=output_dir,
                model=args.model,
                trials=args.trials,
                harness=args.harness,
                harness_bin=args.harness_bin,
                pi_bin=args.pi_bin,
                timeout_seconds=args.timeout_seconds,
                judge_model=args.judge_model,
                judge_timeout_seconds=args.judge_timeout_seconds,
                observer=args.observer,
            )
    except (
        OSError,
        RuntimeError,
        ValueError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("ERROR: evaluation cancelled; partial evidence was preserved", file=sys.stderr)
        return 130
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
