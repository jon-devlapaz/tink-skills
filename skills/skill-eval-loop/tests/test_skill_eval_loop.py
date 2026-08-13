from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from aggregate_benchmark import _usage_bucket, aggregate  # noqa: E402
from audit_suite import audit  # noqa: E402
from eval_runtime import HeadlessEvalRun  # noqa: E402
from eval_spec import (  # noqa: E402
    canonical_sha256,
    grade_case,
    harness_invocation_counts,
    load_suite,
)
from herdr_runtime import HerdrEvalRun, PaneSet, _run_job  # noqa: E402
from model_grader import _parse_grade  # noqa: E402
from process_control import CapturedKeyboardInterrupt, run_captured  # noqa: E402
from recommend_models import (  # noqa: E402
    ModelOption,
    build_recommendation,
    infer_tier,
    parse_pi_models,
)
from run_skill_eval import (  # noqa: E402
    _grade_counter_reference,
    _run_condition,
    _validate_references,
    condition_order,
    plan_run,
    run_suite,
)
from runtime_adapters import (  # noqa: E402
    HARNESS_NAMES,
    build_invocation,
    build_judge_invocation,
    model_matches,
    skill_payload_sha256,
    trace_metadata,
    validate_pinned_model,
)
from runtime_attestation import (  # noqa: E402
    evaluate_target_trace_attestation,
    require_target_runtime_attestation,
)
from workspace_paths import DEFAULT_EVAL_RUNS_ROOT, default_run_output  # noqa: E402


class _FakeHerdrRun:
    def __init__(self, root: Path) -> None:
        self.observer = "herdr"
        self.workspace_id = "fake-workspace"
        self.workspace_label = f"eval:fixture-skill:{root.name}"
        self.roles: list[str] = []
        self.finishes: list[str] = []

    def run_captured(
        self,
        command,
        *,
        cwd,
        env,
        timeout_seconds,
        pane_role,
        title,
        trace_path,
        stderr_path,
    ):
        self.roles.append(pane_role)
        completed, timed_out = run_captured(
            command,
            cwd=cwd,
            env=env,
            timeout_seconds=timeout_seconds,
        )
        trace_path.parent.mkdir(parents=True, exist_ok=True)
        trace_path.write_text(completed.stdout, encoding="utf-8")
        stderr_path.write_text(completed.stderr, encoding="utf-8")
        return completed, timed_out

    def finish(self, *, status, summary, artifact_path):
        self.finishes.append(status)

    def cancel_active(self):
        return None


class _InterruptHerdrRun(_FakeHerdrRun):
    def run_captured(self, *args, **kwargs):
        raise KeyboardInterrupt


class WorkflowContractTests(unittest.TestCase):
    def test_missing_evals_require_fresh_subagent_authoring(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        protocol = (
            SKILL_ROOT / "references" / "eval-authoring.md"
        ).read_text(encoding="utf-8")
        self.assertIn("fresh-context subagent", skill_text)
        self.assertIn("leave suite writing out of the main chat", skill_text)
        self.assertIn("write only `<target-skill>/evals/**`", protocol)
        self.assertIn("at least three distinct", protocol)
        self.assertIn("Do not supply the parent conversation", protocol)

    def test_model_choice_and_setup_changes_require_confirmation(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        remediation = (
            SKILL_ROOT / "references" / "setup-remediation.md"
        ).read_text(encoding="utf-8")
        self.assertIn("recommend_models.py", skill_text)
        self.assertIn("Confirm the exact target model", skill_text)
        self.assertIn("explicit yes", remediation)
        self.assertIn("Never ask the user to paste a secret", remediation)

    def test_interaction_asks_one_question_at_a_time(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Ask exactly one open question per message", skill_text)
        self.assertIn("wait for the answer", skill_text)
        self.assertIn("Confirm the judge model", skill_text)
        self.assertIn("separate turn", skill_text)
        self.assertIn("Setup remediation may interrupt", skill_text)
        self.assertIn("stated fix", skill_text)

    def test_harness_claims_link_the_complete_evidence_matrix(self) -> None:
        skill_text = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        matrix = (SKILL_ROOT / "references" / "harness-support.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("harness evidence matrix", skill_text)
        self.assertNotIn("Name every supported harness", skill_text)
        for harness in ("Pi", "Codex", "Claude Code", "Hermes Agent"):
            self.assertIn(f"| {harness} |", matrix)
        self.assertIn("release verification pending", matrix)


class ModelRecommendationTests(unittest.TestCase):
    def test_provider_name_does_not_inflate_model_tier(self) -> None:
        self.assertEqual(infer_tier("provider/ordinary-model"), "balanced")

    def test_marker_substrings_do_not_inflate_model_tier(self) -> None:
        self.assertEqual(infer_tier("provider/gemini-3.1-pro"), "quality")

    def test_pi_inventory_parser_uses_exact_provider_model_ids(self) -> None:
        output = """provider model context max-out thinking images
openai-codex gpt-5.6-luna 272K 128K yes yes
openai-codex gpt-5.6-terra 272K 128K yes yes
openai-codex gpt-5.6-sol 272K 128K yes yes
"""
        self.assertEqual(
            [model.id for model in parse_pi_models(output)],
            [
                "openai-codex/gpt-5.6-luna",
                "openai-codex/gpt-5.6-terra",
                "openai-codex/gpt-5.6-sol",
            ],
        )

    def test_standard_task_recommends_balanced_target_and_quality_judge(self) -> None:
        models = [
            ModelOption("provider/luna", "budget", "fixture"),
            ModelOption("provider/terra", "balanced", "fixture"),
            ModelOption("provider/sol", "quality", "fixture"),
        ]
        report = build_recommendation(
            harness="pi",
            models=models,
            task_profile="standard",
            case_count=4,
            model_rubric_count=2,
        )
        self.assertEqual(report["recommended_target"], "provider/terra")
        self.assertEqual(report["recommended_judge"], "provider/sol")
        self.assertEqual(report["pilot_harness_invocations"], 14)
        self.assertEqual(report["provider_model_calls"], "unknown")
        self.assertTrue(report["confirmation_required"])

    def test_portability_recommends_a_cross_tier_matrix(self) -> None:
        models = [
            ModelOption("provider/mini", "budget", "fixture"),
            ModelOption("provider/main", "balanced", "fixture"),
            ModelOption("provider/max", "quality", "fixture"),
        ]
        report = build_recommendation(
            harness="codex",
            models=models,
            task_profile="portability",
            case_count=3,
            model_rubric_count=0,
        )
        self.assertEqual(
            report["recommended_targets"],
            ["provider/mini", "provider/main", "provider/max"],
        )
        self.assertIsNone(report["recommended_judge"])

    def test_missing_tier_is_disclosed_as_a_fallback(self) -> None:
        report = build_recommendation(
            harness="hermes",
            models=[ModelOption("provider/main", "balanced", "fixture")],
            task_profile="complex",
            case_count=1,
            model_rubric_count=0,
        )
        self.assertTrue(report["frontier_fallbacks"]["quality"])
        self.assertEqual(report["recommended_target"], "provider/main")

    def test_subset_counter_references_use_per_case_counts(self) -> None:
        models = [ModelOption("provider/main", "balanced", "fixture")]
        report = build_recommendation(
            harness="pi",
            models=models,
            task_profile="standard",
            case_count=3,
            model_rubric_count=3,
            counter_reference_count=2,
            trials=3,
            model_rubric_counts=[2, 1, 0],
            counter_reference_declared=[False, True, True],
        )
        self.assertEqual(
            report["pilot_harness_invocation_counts"],
            {
                "target": 18,
                "condition_judges": 18,
                "references": 3,
                "counter_references": 1,
                "judge": 22,
                "total": 40,
            },
        )

    def test_counter_references_require_exact_per_case_vectors(self) -> None:
        with self.assertRaisesRegex(ValueError, "exact per-case vectors"):
            build_recommendation(
                harness="pi",
                models=[ModelOption("provider/main", "balanced", "fixture")],
                task_profile="standard",
                case_count=2,
                model_rubric_count=1,
                counter_reference_count=1,
            )

    def test_invocation_counts_require_positive_integer_trials(self) -> None:
        for trials in (True, 1.5, 0, -1):
            with self.subTest(trials=trials):
                with self.assertRaisesRegex(ValueError, "positive integer"):
                    harness_invocation_counts(
                        trials=trials,
                        model_rubric_counts=[1],
                        counter_reference_declared=[False],
                    )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _grading(passed: bool = True) -> dict:
    return {
        "grader": {"kind": "deterministic_mixed", "schema_version": 2},
        "expectations": [
            {
                "text": "Completes the task",
                "passed": passed,
                "evidence": "fixture",
                "grader": "response_contains",
            }
        ],
        "summary": {
            "passed": int(passed),
            "failed": int(not passed),
            "total": 1,
            "pass_rate": float(passed),
        },
    }


def _make_record(
    root: Path,
    *,
    skill_name: str,
    condition: str,
    trial: int,
    passed: bool,
    model: str,
) -> dict:
    condition_dir = root / "eval-case" / f"trial-{trial:03d}" / condition
    outputs = condition_dir / "outputs"
    outputs.mkdir(parents=True)
    trace = outputs / "trace.jsonl"
    response = outputs / "response.md"
    grading = condition_dir / "grading.json"
    trace.write_text(
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": model,
                "session_id": f"fixture-{condition}-{trial}",
                "skills": [skill_name] if condition == "with_skill" else [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    response.write_text("done\n" if passed else "not done\n", encoding="utf-8")
    _write_json(grading, _grading(passed))
    installed = ""
    available: list[str] = []
    if condition == "with_skill":
        skill = condition_dir / "installed-skill" / skill_name
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: fixture\n---\n",
            encoding="utf-8",
        )
        installed = str(skill.relative_to(root))
        available = [skill_name]
    return {
        "case_id": "case",
        "trial": trial,
        "condition": condition,
        "duration_seconds": 0.1,
        "exit_code": 0,
        "timed_out": False,
        "requested_model": model,
        "actual_model": model,
        "available_skills": available,
        "skill_available": condition == "with_skill",
        "skill_activation": (
            "forced_command" if condition == "with_skill" else "none"
        ),
        "installed_skill_path": installed,
        "skill_injection_attested": condition == "with_skill",
        "skill_explicitly_accessed": False,
        "expected_skill_loading": (
            "required" if condition == "with_skill" else "forbidden"
        ),
        "total_tokens": 10,
        "cost": 0.01,
        "trace_path": str(trace.relative_to(root)),
        "trace_sha256": _sha256(trace),
        "response_path": str(response.relative_to(root)),
        "response_sha256": _sha256(response),
        "grading_path": str(grading.relative_to(root)),
        "grading_sha256": _sha256(grading),
    }


def _make_judge_record(root: Path, *, name: str, model: str) -> dict:
    trace = root / "judges" / f"{name}.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(
        json.dumps(
            {
                "type": "system",
                "subtype": "init",
                "model": model,
                "session_id": f"judge-{name}",
                "skills": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "actual_model": model,
        "trace_path": str(trace.relative_to(root)),
        "trace_sha256": _sha256(trace),
        "total_tokens": 2,
        "cost": 0.02,
    }


def _make_run(root: Path, outcomes: list[tuple[bool, bool]]) -> None:
    skill_name = "candidate"
    model = "provider/model-1"
    pairs = []
    for trial, (without, with_skill) in enumerate(outcomes, start=1):
        conditions = {
            "without_skill": _make_record(
                root,
                skill_name=skill_name,
                condition="without_skill",
                trial=trial,
                passed=without,
                model=model,
            ),
            "with_skill": _make_record(
                root,
                skill_name=skill_name,
                condition="with_skill",
                trial=trial,
                passed=with_skill,
                model=model,
            ),
        }
        pairs.append({"case_id": "case", "trial": trial, "conditions": conditions})
    installed = (
        root
        / "eval-case"
        / "trial-001"
        / "with_skill"
        / "installed-skill"
        / skill_name
    )
    suite = root / "suite_snapshot.json"
    _write_json(
        suite,
        {
            "schema_version": 2,
            "skill_name": skill_name,
            "cases": [{"id": "case"}],
        },
    )
    _write_json(
        root / "run_manifest.json",
        {
            "schema_version": 1,
            "target_skill_name": skill_name,
            "skill_sha256": skill_payload_sha256(installed),
            "suite_path": "suite_snapshot.json",
            "suite_sha256": _sha256(suite),
            "provenance_path": None,
            "provenance_sha256": None,
            "requested_model": model,
            "harness": "pi",
            "case_count": 1,
            "trials_per_case": len(pairs),
            "pair_count": len(pairs),
            "trials": pairs,
        },
    )


def _make_sealed_marker_run(root: Path) -> None:
    fixture = SKILL_ROOT / "tests" / "fixtures" / "sealed-marker"
    nonce = "integrity-0001"
    prompt = (fixture / "prompt.txt").read_text(encoding="utf-8").strip()
    skill_text = (fixture / "skill-template.md").read_text(encoding="utf-8")
    skill_text = skill_text.replace("{{RUN_NONCE}}", nonce)
    marker = {
        "schema": "acme.sealed-marker/v1",
        "status": "ready",
        "owner": f"skillbench-causal-pilot-{nonce}",
    }
    graders = [
        {
            "name": "Creates the sealed marker",
            "type": "file_exists",
            "path": ".acme/sealed-marker.json",
        },
        {
            "name": "Uses the exact sealed marker value",
            "type": "json_exact",
            "path": ".acme/sealed-marker.json",
            "expected": marker,
        },
    ]

    _make_run(root, [(False, True), (False, True)])
    for trial in range(1, 3):
        for condition in ("without_skill", "with_skill"):
            condition_dir = root / "eval-case" / f"trial-{trial:03d}" / condition
            response = condition_dir / "outputs" / "response.md"
            response.write_text(
                "sealed marker prepared\n" if condition == "with_skill" else "unable\n",
                encoding="utf-8",
            )
            if condition == "with_skill":
                _write_json(condition_dir / ".acme" / "sealed-marker.json", marker)
                installed = condition_dir / "installed-skill" / "candidate" / "SKILL.md"
                installed.write_text(skill_text, encoding="utf-8")
            grading = grade_case(
                workspace=condition_dir,
                response=response.read_text(encoding="utf-8"),
                graders=graders,
            )
            grading_path = condition_dir / "grading.json"
            _write_json(grading_path, grading)

    manifest_path = root / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    installed = (
        root
        / "eval-case"
        / "trial-001"
        / "with_skill"
        / "installed-skill"
        / "candidate"
    )
    manifest["skill_sha256"] = skill_payload_sha256(installed)
    for pair in manifest["trials"]:
        for condition in ("without_skill", "with_skill"):
            record = pair["conditions"][condition]
            condition_dir = (
                root
                / "eval-case"
                / f"trial-{pair['trial']:03d}"
                / condition
            )
            record["response_sha256"] = _sha256(
                condition_dir / "outputs" / "response.md"
            )
            record["grading_sha256"] = _sha256(condition_dir / "grading.json")

    suite_path = root / "suite_snapshot.json"
    suite = json.loads(suite_path.read_text(encoding="utf-8"))
    suite["cases"][0]["prompt"] = prompt
    _write_json(suite_path, suite)
    manifest["suite_sha256"] = _sha256(suite_path)
    _write_json(manifest_path, manifest)


def _make_schema2_skill(root: Path) -> Path:
    skill = root / "fixture-skill"
    (skill / "evals").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: fixture-skill\ndescription: fixture\n---\n",
        encoding="utf-8",
    )
    _write_json(
        skill / "evals" / "evals.json",
        {
            "schema_version": 2,
            "skill_name": "fixture-skill",
            "suite_type": "regression",
            "dataset_origin": "author_derived",
            "tool_profile": "no_tools",
            "evals": [
                {
                    "id": "case",
                    "behavior_class": "positive",
                    "prompt": "Return done.",
                    "expected_skill_loading": "required",
                    "graders": [
                        {
                            "name": "Returns done",
                            "type": "response_contains",
                            "value": "done",
                        }
                    ],
                    "reference": {"response": "done"},
                }
            ],
        },
    )
    return skill


def _make_schema3_skill(root: Path, *, tamper: bool = False) -> Path:
    skill = root / "candidate-skill"
    provenance_dir = skill / "evals" / "provenance"
    provenance_dir.mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: candidate-skill\ndescription: fixture\n---\n",
        encoding="utf-8",
    )
    artifact = provenance_dir / "source.json"
    _write_json(artifact, {"source": "test fixture"})
    case = {
        "id": "case",
        "behavior_class": "positive",
        "routing_class": "should_trigger",
        "prompt": "Return done.",
        "expected_skill_loading": "required",
        "graders": [
            {
                "name": "Returns done",
                "type": "response_contains",
                "value": "done",
            }
        ],
        "reference": {"response": "done"},
        "counter_reference": {"response": "wrong"},
    }
    suite = {
        "schema_version": 3,
        "skill_name": "candidate-skill",
        "suite_type": "regression",
        "dataset_origin": "author_derived",
        "tool_profile": "no_tools",
        "grader_discrimination": "case_contrast",
        "provenance_manifest": "provenance.json",
        "distribution_policy": {
            "minimum_pairs": 3,
            "minimum_effect_size": 0.1,
            "confidence_level": 0.95,
        },
        "evals": [case],
    }
    _write_json(skill / "evals" / "evals.json", suite)
    _write_json(
        skill / "evals" / "provenance.json",
        {
            "schema_version": 1,
            "suite_sha256": canonical_sha256(suite),
            "cases": [
                {
                    "case_id": "case",
                    "origin": "author_derived",
                    "source_id": "fixture-1",
                    "source_type": "author_scenario",
                    "observed_at": "2026-07-29",
                    "task_author": "test",
                    "artifact": "provenance/source.json",
                    "artifact_sha256": _sha256(artifact),
                    "case_sha256": canonical_sha256(case),
                }
            ],
        },
    )
    if tamper:
        _write_json(artifact, {"source": "changed after registration"})
    return skill


class SuiteAuditTests(unittest.TestCase):
    def test_valid_provenance_suite_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = audit(_make_schema3_skill(Path(temp)))
            self.assertTrue(report["valid"])
            self.assertEqual(report["provenance_case_count"], 1)
            self.assertEqual(
                report["grader_discrimination"],
                {
                    "claim": "case_contrast",
                    "contrast_case_count": 1,
                    "response_sensitive_grader_count": 1,
                    "deterministic_graders_checked": 1,
                    "model_graders_pending_runtime": 0,
                },
            )

    def test_missing_schema_three_contrast_fails_with_actionable_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0].pop("counter_reference")
            _write_json(suite_path, suite)
            report = audit(skill)
            self.assertFalse(report["valid"])
            self.assertEqual(report["errors"], ["missing_grader_contrast"])

    def test_non_discriminating_contrast_fails_with_actionable_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["counter_reference"] = {"response": "done"}
            _write_json(suite_path, suite)
            report = audit(skill)
            self.assertFalse(report["valid"])
            self.assertEqual(
                report["errors"],
                ["non_discriminating_grader_contrast"],
            )

    def test_contrast_claim_with_only_workspace_graders_fails_audit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "Creates the result",
                    "type": "file_exists",
                    "path": "result.json",
                }
            ]
            suite["evals"][0].pop("counter_reference")
            _write_json(suite_path, suite)
            report = audit(skill)
            self.assertFalse(report["valid"])
            self.assertEqual(
                report["errors"],
                ["non_discriminating_grader_contrast"],
            )
            self.assertIn(
                "requires at least one response-sensitive grader",
                report["details"][0],
            )

    def test_malformed_contrast_fails_with_actionable_code(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["counter_reference"] = {"response": 7}
            _write_json(suite_path, suite)
            report = audit(skill)
            self.assertFalse(report["valid"])
            self.assertEqual(report["errors"], ["invalid_grader_contrast"])
            self.assertIn("must be a string", report["details"][0])

    def test_schema_three_without_a_discrimination_claim_remains_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            provenance_path = skill / "evals" / "provenance.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite.pop("grader_discrimination")
            _write_json(suite_path, suite)
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["suite_sha256"] = canonical_sha256(suite)
            _write_json(provenance_path, provenance)
            report = audit(skill)
            self.assertTrue(report["valid"])
            self.assertEqual(report["grader_discrimination"]["claim"], "none")
            self.assertEqual(
                report["grader_discrimination"]["contrast_case_count"],
                0,
            )

    def test_tampered_provenance_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = audit(_make_schema3_skill(Path(temp), tamper=True))
            self.assertFalse(report["valid"])
            self.assertEqual(report["errors"], ["provenance_hash_mismatch"])


class SuiteValidationTests(unittest.TestCase):
    def test_duplicate_grader_names_are_rejected_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            duplicate = dict(suite["evals"][0]["graders"][0])
            suite["evals"][0]["graders"].append(duplicate)
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(ValueError, "duplicate grader name"):
                load_suite(skill)

    def test_schema_two_model_grader_requires_rubric(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "criteria only",
                    "type": "model_rubric",
                    "criteria": [{"requirement": "Do it"}],
                }
            ]
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(ValueError, "rubric"):
                load_suite(skill)


class DeclaredPolicyTests(unittest.TestCase):
    """A declared distribution_policy is recorded and reported as unapplied.

    The schema requires the field and validates its bounds, but no evaluator
    decision uses it. Saying so in the run artifact keeps it from reading like a
    threshold the run enforced.
    """

    def test_limits_name_the_policy_that_did_not_gate_the_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(True, False), (True, False), (True, True)])
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["distribution_policy"] = {
                "minimum_pairs": 3,
                "minimum_effect_size": 0.1,
                "confidence_level": 0.95,
            }
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(snapshot_path)
            _write_json(manifest_path, manifest)

            limits = aggregate(root)["limits"]
            policy_notes = [line for line in limits if "distribution_policy" in line]
            self.assertEqual(len(policy_notes), 1)
            self.assertIn("not applied", policy_notes[0])
            self.assertIn("minimum_effect_size=0.1", policy_notes[0])

    def test_a_run_without_a_declared_policy_gains_no_note(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(True, False), (True, False), (True, True)])
            limits = aggregate(root)["limits"]
            self.assertFalse([line for line in limits if "distribution_policy" in line])

    def test_run_suite_retains_declared_policy_in_the_snapshot(self) -> None:
        """Honesty depends on run_suite writing the field, not only aggregate.

        The aggregate-only fixtures above can stay green if the snapshot write is
        dropped. A schema-3 fake run proves the production path retains the
        declared policy and names it as unapplied in limits.
        """
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema3_skill(root)
            fake_pi = root / "fake-pi"
            fake_pi.write_text(
                """#!/usr/bin/env python3
import json
import sys

if "--version" in sys.argv:
    print("fake-pi 1.0")
    raise SystemExit(0)

treatment = "--skill" in sys.argv
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/model-1",
    "session_id": "fixture-session",
    "skills": ["candidate-skill"] if treatment else [],
}))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/model-1",
        "content": [{"type": "text", "text": "done" if treatment else "FAIL"}],
        "usage": {"input": 1, "output": 1, "totalTokens": 2},
    }
}))
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            output = root / "run"
            report = run_suite(
                skill_path=skill,
                output_dir=output,
                model="provider/model-1",
                trials=1,
                pi_bin=str(fake_pi),
            )
            snapshot = json.loads(
                (output / "suite_snapshot.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                snapshot["distribution_policy"],
                {
                    "minimum_pairs": 3,
                    "minimum_effect_size": 0.1,
                    "confidence_level": 0.95,
                },
            )
            self.assertEqual(snapshot["cases"][0]["model_rubric_count"], 0)
            self.assertEqual(
                snapshot["cases"][0]["response_sensitive_graders"],
                [{"name": "Returns done", "type": "response_contains"}],
            )
            self.assertTrue(snapshot["cases"][0]["counter_reference_declared"])
            self.assertEqual(
                report["grader_discrimination"],
                {"claim": "case_contrast", "validated": True},
            )
            policy_notes = [
                line for line in report["limits"] if "distribution_policy" in line
            ]
            self.assertEqual(len(policy_notes), 1)
            self.assertIn("not applied", policy_notes[0])
            self.assertIn("minimum_effect_size=0.1", policy_notes[0])


class CounterReferenceTests(unittest.TestCase):
    """A declared counter-reference must fail the graders.

    The existing reference check proves the graders accept a correct answer. It
    cannot show they reject a wrong one, and graders that accept everything
    report a confident verdict for both conditions of a paired run.
    """

    def _skill_with_counter(self, root: Path, counter_response: str) -> Path:
        """Add a counter-reference and re-register the case.

        A counter-reference is part of the case, so it changes the case hash.
        Re-registering it here is the same step an author takes when editing a
        suite; leaving the manifest stale would fail provenance, which is the
        behaviour we want everywhere else.
        """
        skill = _make_schema3_skill(root)
        suite_path = skill / "evals" / "evals.json"
        provenance_path = skill / "evals" / "provenance.json"
        suite = json.loads(suite_path.read_text(encoding="utf-8"))
        suite["evals"][0]["counter_reference"] = {"response": counter_response}
        _write_json(suite_path, suite)

        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["suite_sha256"] = canonical_sha256(suite)
        provenance["cases"][0]["case_sha256"] = canonical_sha256(suite["evals"][0])
        _write_json(provenance_path, provenance)
        return skill

    def _validate(self, skill: Path, output_dir: Path) -> list[dict]:
        suite = load_suite(skill)
        return _validate_references(
            suite_root=skill / "evals",
            suite=suite,
            output_dir=output_dir,
            harness="pi",
            executable="unused",
            judge_model=None,
            judge_timeout_seconds=1,
            eval_run=None,
        )

    def test_a_wrong_counter_reference_is_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = self._skill_with_counter(root, "this answer is wrong")
            self.assertTrue(self._validate(skill, root / "out"))

    def test_a_model_grader_that_accepts_the_counter_stops_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = self._skill_with_counter(root, "this answer is wrong")
            suite_path = skill / "evals" / "evals.json"
            provenance_path = skill / "evals" / "provenance.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"].append(
                {
                    "name": "Judge",
                    "type": "model_rubric",
                    "rubric": "done",
                    "criteria": [
                        {
                            "requirement": "Returns done",
                            "prompt_quote": "Return done.",
                        }
                    ],
                }
            )
            _write_json(suite_path, suite)
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["suite_sha256"] = canonical_sha256(suite)
            provenance["cases"][0]["case_sha256"] = canonical_sha256(
                suite["evals"][0]
            )
            _write_json(provenance_path, provenance)
            passing_grade = {"Judge": {"passed": True, "evidence": "fixture"}}
            with (
                patch(
                    "run_skill_eval._model_graders",
                    return_value=(passing_grade, []),
                ),
                self.assertRaisesRegex(
                    ValueError,
                    "counter-reference did not fail response-sensitive graders: Judge",
                ),
            ):
                self._validate(skill, root / "out")

    def test_schema_three_response_graders_require_a_counter_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema3_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0].pop("counter_reference")
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(ValueError, "counter_reference is required"):
                load_suite(skill)

    def test_schema_two_without_a_counter_reference_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            case = load_suite(skill)["evals"][0]
            self.assertIsNone(
                _grade_counter_reference(
                    case=case,
                    suite_root=skill,
                    output_dir=root / "out",
                    harness="pi",
                    executable="unused",
                    judge_model=None,
                    judge_timeout_seconds=1,
                    eval_run=None,
                )
            )

    @patch("run_skill_eval._model_graders")
    def test_counter_reference_retains_its_judge_records(self, graders) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = self._skill_with_counter(root, "this answer is wrong")
            suite_path = skill / "evals" / "evals.json"
            provenance_path = skill / "evals" / "provenance.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"].append(
                {
                    "name": "Judge",
                    "type": "model_rubric",
                    "rubric": "done",
                    "criteria": [
                        {"requirement": "Returns done", "prompt_quote": "Return done."}
                    ],
                }
            )
            _write_json(suite_path, suite)
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["suite_sha256"] = canonical_sha256(suite)
            provenance["cases"][0]["case_sha256"] = canonical_sha256(suite["evals"][0])
            _write_json(provenance_path, provenance)
            judge_record = {
                "actual_model": "provider/judge-1",
                "trace_path": "judge.jsonl",
            }
            graders.side_effect = (
                (
                    {"Judge": {"passed": True, "evidence": "fixture"}},
                    [judge_record],
                ),
                (
                    {"Judge": {"passed": False, "evidence": "fixture"}},
                    [judge_record],
                ),
            )
            records = self._validate(skill, root / "out")
            self.assertEqual(
                records[0]["counter_reference"]["judge_records"],
                [{"actual_model": "provider/judge-1", "trace_path": "judge.jsonl"}],
            )

    def test_counter_reference_must_be_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["counter_reference"] = "wrong"
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(ValueError, "counter_reference must be an object"):
                load_suite(skill)

    def test_counter_reference_response_must_be_a_string(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["counter_reference"] = {"response": 7}
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(ValueError, "counter_reference.response must be a string"):
                load_suite(skill)

    def test_empty_counter_reference_object_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["counter_reference"] = {}
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(
                ValueError, "counter_reference.response is required"
            ):
                load_suite(skill)

    def test_counter_reference_requires_a_response_sensitive_grader(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema3_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "Creates the result",
                    "type": "file_exists",
                    "path": "result.json",
                }
            ]
            suite["evals"][0]["counter_reference"] = {"response": "wrong"}
            _write_json(suite_path, suite)
            with self.assertRaisesRegex(
                ValueError, "requires at least one response-sensitive grader"
            ):
                load_suite(skill)


class TargetAttestationOwnerTests(unittest.TestCase):
    def _ok_metadata(self, **overrides: object) -> dict:
        metadata = {
            "attestation_trace_path": Path("/tmp/rollout.jsonl"),
            "model_attested": True,
            "actual_model": "provider/model-1",
            "skill_explicitly_accessed": True,
        }
        metadata.update(overrides)
        return metadata

    def test_evaluate_passes_when_attested(self) -> None:
        reasons = evaluate_target_trace_attestation(
            self._ok_metadata(),
            harness="codex",
            requested_model="provider/model-1",
            recorded_actual_model="provider/model-1",
        )
        self.assertEqual(reasons, [])

    def test_evaluate_reports_codex_rollout_missing(self) -> None:
        reasons = evaluate_target_trace_attestation(
            self._ok_metadata(attestation_trace_path=None, model_attested=False),
            harness="codex",
            requested_model="provider/model-1",
        )
        self.assertIn("attestation_trace_missing", reasons)
        self.assertIn("model_not_attested", reasons)

    def test_evaluate_reports_manifest_model_mismatch(self) -> None:
        reasons = evaluate_target_trace_attestation(
            self._ok_metadata(actual_model="provider/other"),
            harness="codex",
            requested_model="provider/model-1",
            recorded_actual_model="provider/model-1",
        )
        self.assertIn("model_mismatch", reasons)
        self.assertIn("manifest_model_mismatch", reasons)

    def test_evaluate_fail_closed_on_empty_recorded_model(self) -> None:
        reasons = evaluate_target_trace_attestation(
            self._ok_metadata(),
            harness="codex",
            requested_model="provider/model-1",
            recorded_actual_model="",
        )
        self.assertIn("manifest_model_mismatch", reasons)

    def test_require_raises_when_forced_skill_not_accessed(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "forced target skill fixture-skill was not explicitly accessed",
        ):
            require_target_runtime_attestation(
                self._ok_metadata(skill_explicitly_accessed=False),
                harness="codex",
                requested_model="provider/model-1",
                condition="with_skill",
                activation_mode="forced",
                skill_name="fixture-skill",
                trace_path=Path("/tmp/trace.jsonl"),
            )

    def test_require_skips_forced_skill_outside_codex_forced_treatment(self) -> None:
        require_target_runtime_attestation(
            self._ok_metadata(skill_explicitly_accessed=False),
            harness="pi",
            requested_model="provider/model-1",
            condition="with_skill",
            activation_mode="forced",
            skill_name="fixture-skill",
            trace_path=Path("/tmp/trace.jsonl"),
        )

    def test_evaluate_reports_forced_skill_when_write_context_supplied(self) -> None:
        reasons = evaluate_target_trace_attestation(
            self._ok_metadata(skill_explicitly_accessed=False),
            harness="codex",
            requested_model="provider/model-1",
            condition="with_skill",
            activation_mode="forced",
        )
        self.assertEqual(reasons, ["forced_skill_not_accessed"])

    def test_require_maps_evaluate_reasons_to_runtime_errors(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            "requested target model provider/model-1 but attested provider/other",
        ):
            require_target_runtime_attestation(
                self._ok_metadata(actual_model="provider/other"),
                harness="codex",
                requested_model="provider/model-1",
                condition="without_skill",
                activation_mode="forced",
                skill_name="fixture-skill",
                trace_path=Path("/tmp/trace.jsonl"),
            )

    def test_require_reports_cross_provider_same_leaf_mismatch(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            (
                "requested target model provider-a/model-1 but attested "
                "provider-b/model-1"
            ),
        ):
            require_target_runtime_attestation(
                self._ok_metadata(actual_model="provider-b/model-1"),
                harness="codex",
                requested_model="provider-a/model-1",
                condition="without_skill",
                activation_mode="forced",
                skill_name="fixture-skill",
                trace_path=Path("/tmp/trace.jsonl"),
            )


class RuntimeTests(unittest.TestCase):
    def test_model_identity_requires_the_full_provider_and_model(self) -> None:
        self.assertTrue(
            model_matches(" Provider/GPT-5.6-Terra ", "provider/gpt-5.6-terra")
        )
        self.assertFalse(
            model_matches("provider/gpt-5.6-terra", "gpt-5.6-terra")
        )
        self.assertFalse(
            model_matches("provider-a/model-1", "provider-b/model-1")
        )
        self.assertFalse(
            model_matches("provider/model-1", "provider/model-1-preview")
        )
        self.assertFalse(model_matches("gpt-5.6", "gpt-5.6-evil"))

    def test_harness_choices_are_explicit_and_complete(self) -> None:
        self.assertEqual(
            HARNESS_NAMES,
            ("hermes", "claude-code", "codex", "pi"),
        )

    def test_skill_payload_rejects_symlinked_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            secret = root / "outside.txt"
            secret.write_text("do not expose\n", encoding="utf-8")
            (skill / "references").mkdir()
            (skill / "references" / "linked.txt").symlink_to(secret)
            with self.assertRaisesRegex(ValueError, "symlink"):
                skill_payload_sha256(skill)

    def test_skill_payload_digest_includes_executable_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            script = skill / "scripts" / "run.sh"
            script.parent.mkdir()
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            script.chmod(0o644)
            plain_digest = skill_payload_sha256(skill)
            script.chmod(0o755)
            executable_digest = skill_payload_sha256(skill)
            self.assertNotEqual(plain_digest, executable_digest)

    def test_each_harness_isolates_the_skill_to_treatment(self) -> None:
        expected_markers = {
            "hermes": "--skills",
            "claude-code": "/fixture-skill",
            "codex": "$fixture-skill",
            "pi": "--skill",
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            for harness, marker in expected_markers.items():
                with self.subTest(harness=harness):
                    treatment = build_invocation(
                        harness=harness,
                        executable=harness,
                        condition="with_skill",
                        condition_dir=root / harness / "with",
                        skill_path=skill,
                        prompt="Return done.",
                        model="provider/model-1",
                        tool_profile="no_tools",
                    )
                    control = build_invocation(
                        harness=harness,
                        executable=harness,
                        condition="without_skill",
                        condition_dir=root / harness / "without",
                        skill_path=skill,
                        prompt="Return done.",
                        model="provider/model-1",
                        tool_profile="no_tools",
                    )
                    self.assertIn(marker, " ".join(treatment.command))
                    self.assertNotIn(marker, " ".join(control.command))
                    self.assertEqual(treatment.available_skills, ["fixture-skill"])
                    self.assertEqual(control.available_skills, [])
                    self.assertIsNotNone(treatment.installed_skill_path)
                    self.assertIsNone(control.installed_skill_path)
                    self.assertEqual(treatment.exposed_tools, control.exposed_tools)

    def test_each_harness_builds_a_skill_free_judge(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for harness in HARNESS_NAMES:
                with self.subTest(harness=harness):
                    invocation = build_judge_invocation(
                        harness=harness,
                        executable=harness,
                        model="provider/model-1",
                        prompt="Return JSON.",
                        run_dir=root / harness,
                    )
                    command = " ".join(invocation.command).lower()
                    self.assertEqual(invocation.available_skills, [])
                    self.assertEqual(invocation.exposed_tools, [])
                    self.assertNotIn("fixture-skill", command)

    def test_pi_changes_only_explicit_skill_availability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            treatment = build_invocation(
                executable="pi",
                condition="with_skill",
                condition_dir=root / "with",
                skill_path=skill,
                prompt="Return done.",
                model="provider/model-1",
                tool_profile="no_tools",
            )
            control = build_invocation(
                executable="pi",
                condition="without_skill",
                condition_dir=root / "without",
                skill_path=skill,
                prompt="Return done.",
                model="provider/model-1",
                tool_profile="no_tools",
            )
            self.assertIn("--no-skills", treatment.command)
            self.assertIn("--skill", treatment.command)
            self.assertNotIn("--skill", control.command)
            self.assertEqual(treatment.exposed_tools, control.exposed_tools)
            self.assertEqual(treatment.available_skills, ["fixture-skill"])
            self.assertEqual(control.available_skills, [])
            self.assertEqual(
                treatment.command[-1],
                "/skill:fixture-skill Return done.",
            )
            self.assertEqual(control.command[-1], "Return done.")
            self.assertFalse((treatment.installed_skill_path / "evals").exists())

    def test_autonomous_mode_leaves_the_treatment_task_unexpanded(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            treatment = build_invocation(
                executable="pi",
                condition="with_skill",
                condition_dir=root / "with",
                skill_path=skill,
                prompt="Return done.",
                model="provider/model-1",
                tool_profile="read_only",
                activation_mode="autonomous",
            )
            self.assertEqual(treatment.command[-1], "Return done.")
            self.assertIn("--skill", treatment.command)
            self.assertEqual(
                treatment.skill_activation,
                "available_for_autonomous_selection",
            )
            self.assertEqual(
                treatment.exposed_tools,
                ["read", "grep", "find", "ls"],
            )

    def test_moving_model_aliases_are_rejected(self) -> None:
        for model in ("auto", "default", "provider/latest"):
            with self.assertRaises(ValueError):
                validate_pinned_model(model)

    def test_trace_separates_injection_from_explicit_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.jsonl"
            trace.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "type": "system",
                                "subtype": "init",
                                "skills": ["fixture-skill"],
                            }
                        ),
                        json.dumps(
                            {
                                "type": "message",
                                "message": {
                                    "role": "assistant",
                                    "content": [{"type": "text", "text": "done"}],
                                },
                            }
                        ),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(trace, "fixture-skill")
            self.assertTrue(metadata["skill_injection_attested"])
            self.assertFalse(metadata["skill_explicitly_accessed"])

    def test_trace_does_not_infer_actual_model_from_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.txt"
            trace.write_text("plain harness response\n", encoding="utf-8")
            metadata = trace_metadata(
                trace,
                "",
                harness="hermes",
                requested_model="provider/requested-model",
            )
            self.assertEqual(metadata["actual_model"], "")
            self.assertFalse(metadata["model_attested"])

    def test_hermes_no_tools_uses_an_explicit_disabled_toolset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            condition_dir = root / "condition"
            invocation = build_invocation(
                harness="hermes",
                executable="hermes",
                condition="with_skill",
                condition_dir=condition_dir,
                skill_path=skill,
                prompt="task",
                model="provider/model-1",
                tool_profile="no_tools",
            )
            config = json.loads(
                (condition_dir / "hermes-config.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(config["agent"]["disabled_toolsets"], ["file"])
            self.assertEqual(invocation.tool_enforcement, "disabled_toolset")
            self.assertNotIn("--source", invocation.command)

    def test_codex_uses_an_isolated_codex_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            condition_dir = root / "condition"
            invocation = build_invocation(
                harness="codex",
                executable="codex",
                condition="without_skill",
                condition_dir=condition_dir,
                skill_path=skill,
                prompt="task",
                model="gpt-5.6-terra",
                tool_profile="no_tools",
            )
            self.assertEqual(
                invocation.env["CODEX_HOME"],
                str(condition_dir / "codex-home"),
            )
            self.assertEqual(invocation.tool_enforcement, "sandbox_posture_only")

    def test_codex_persists_session_for_runtime_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            invocation = build_invocation(
                harness="codex",
                executable="codex",
                condition="with_skill",
                condition_dir=root / "condition",
                skill_path=skill,
                prompt="task",
                model="gpt-5.6-terra",
                tool_profile="no_tools",
            )
            judge = build_judge_invocation(
                harness="codex",
                executable="codex",
                model="gpt-5.6-sol",
                prompt="judge",
                run_dir=root / "judge",
            )
            self.assertNotIn("--ephemeral", invocation.command)
            self.assertNotIn("--ephemeral", judge.command)

    def test_codex_rollout_attests_model_and_skill_availability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / "trace.jsonl"
            trace.write_text(
                json.dumps(
                    {"type": "thread.started", "thread_id": "thread-123"}
                )
                + "\n",
                encoding="utf-8",
            )
            codex_home = root / "codex-home"
            rollout = (
                codex_home
                / "sessions"
                / "2026"
                / "08"
                / "02"
                / "rollout-thread-123.jsonl"
            )
            rollout.parent.mkdir(parents=True)
            rollout.write_text(
                "\n".join(
                    json.dumps(event)
                    for event in (
                        {
                            "type": "turn_context",
                            "payload": {"model": "gpt-5.6-terra"},
                        },
                        {
                            "type": "world_state",
                            "payload": {
                                "state": {
                                    "host_skills": {
                                        "body": (
                                            "- fixture-skill: (file: "
                                            "/tmp/fixture-skill/SKILL.md)"
                                        )
                                    }
                                }
                            },
                        },
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(
                trace,
                "fixture-skill",
                harness="codex",
                requested_model="gpt-5.6-terra",
                codex_home=codex_home,
            )
            self.assertEqual(metadata["actual_model"], "gpt-5.6-terra")
            self.assertTrue(metadata["model_attested"])
            self.assertTrue(metadata["skill_injection_attested"])
            self.assertFalse(metadata["skill_explicitly_accessed"])
            self.assertEqual(metadata["attestation_trace_path"], rollout)

    def test_conflicting_trace_models_fail_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / "trace.jsonl"
            trace.write_text(
                "\n".join(
                    (
                        json.dumps(
                            {
                                "type": "thread.started",
                                "thread_id": "thread-conflict",
                            }
                        ),
                        json.dumps(
                            {
                                "type": "system",
                                "subtype": "init",
                                "model": "gpt-5.6-terra",
                            }
                        ),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            codex_home = root / "codex-home"
            rollout = (
                codex_home
                / "sessions/2026/08/02/rollout-thread-conflict.jsonl"
            )
            rollout.parent.mkdir(parents=True)
            rollout.write_text(
                json.dumps(
                    {
                        "type": "turn_context",
                        "payload": {"model": "gpt-5.6-sol"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(
                trace,
                "",
                harness="codex",
                requested_model="gpt-5.6-terra",
                codex_home=codex_home,
            )
            self.assertEqual(metadata["actual_model"], "")
            self.assertFalse(metadata["model_attested"])
            self.assertTrue(metadata["model_attestation_conflict"])

    def test_same_leaf_models_from_different_providers_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.jsonl"
            trace.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "type": "system",
                            "subtype": "init",
                            "model": model,
                        }
                    )
                    for model in (
                        "provider-a/model-1",
                        "provider-b/model-1",
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(trace, "")
            self.assertEqual(metadata["actual_model"], "")
            self.assertFalse(metadata["model_attested"])
            self.assertTrue(metadata["model_attestation_conflict"])

    def test_pi_trace_combines_separate_provider_and_model_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.jsonl"
            trace.write_text(
                json.dumps(
                    {
                        "type": "message_start",
                        "message": {
                            "role": "assistant",
                            "provider": "openai-codex",
                            "model": "gpt-5.6-sol",
                            "content": [],
                        },
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(trace, "", harness="pi")
            self.assertEqual(metadata["actual_model"], "openai-codex/gpt-5.6-sol")
            self.assertTrue(metadata["model_attested"])
            self.assertFalse(metadata["model_attestation_conflict"])
            self.assertTrue(
                model_matches(
                    "openai-codex/gpt-5.6-sol",
                    metadata["actual_model"],
                )
            )

    def test_pi_trace_conflicting_separate_providers_fail_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trace = Path(temp) / "trace.jsonl"
            trace.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "type": "message_start",
                            "message": {
                                "role": "assistant",
                                "provider": provider,
                                "model": "model-1",
                                "content": [],
                            },
                        }
                    )
                    for provider in ("provider-a", "provider-b")
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(trace, "", harness="pi")
            self.assertEqual(metadata["actual_model"], "")
            self.assertFalse(metadata["model_attested"])
            self.assertTrue(metadata["model_attestation_conflict"])

    def test_codex_skill_catalog_with_description_attests_injection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / "trace.jsonl"
            trace.write_text(
                json.dumps(
                    {"type": "thread.started", "thread_id": "thread-456"}
                )
                + "\n",
                encoding="utf-8",
            )
            codex_home = root / "codex-home"
            rollout = (
                codex_home
                / "sessions/2026/08/02/rollout-thread-456.jsonl"
            )
            rollout.parent.mkdir(parents=True)
            rollout.write_text(
                "\n".join(
                    json.dumps(event)
                    for event in (
                        {
                            "type": "turn_context",
                            "payload": {"model": "gpt-5.6-terra"},
                        },
                        {
                            "type": "world_state",
                            "payload": {
                                "state": {
                                    "host_skills": {
                                        "body": (
                                            "- fixture-skill: Contextual skill "
                                            "description. (file: /tmp/fixture-skill/"
                                            "SKILL.md)"
                                        )
                                    }
                                }
                            },
                        },
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(
                trace,
                "fixture-skill",
                harness="codex",
                requested_model="gpt-5.6-terra",
                codex_home=codex_home,
            )
            self.assertTrue(metadata["skill_injection_attested"])

    def test_codex_structured_skill_payload_attests_explicit_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / "trace.jsonl"
            trace.write_text(
                json.dumps(
                    {"type": "thread.started", "thread_id": "thread-789"}
                )
                + "\n",
                encoding="utf-8",
            )
            codex_home = root / "codex-home"
            installed = (
                root / "workspace/.agents/skills/fixture-skill"
            ).resolve()
            rollout = (
                codex_home
                / "sessions/2026/08/02/rollout-thread-789.jsonl"
            )
            rollout.parent.mkdir(parents=True)
            rollout.write_text(
                "\n".join(
                    json.dumps(event)
                    for event in (
                        {
                            "type": "turn_context",
                            "payload": {"model": "gpt-5.6-terra"},
                        },
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "message",
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": (
                                            "<skill>\n"
                                            "<name>fixture-skill</name>\n"
                                            f"<path>{installed}/SKILL.md</path>\n"
                                            "</skill>"
                                        ),
                                    }
                                ],
                            },
                        },
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            metadata = trace_metadata(
                trace,
                "fixture-skill",
                installed,
                harness="codex",
                requested_model="gpt-5.6-terra",
                codex_home=codex_home,
            )
            self.assertTrue(metadata["skill_explicitly_accessed"])


class ProcessControlTests(unittest.TestCase):
    def test_timeout_terminates_process_group(self) -> None:
        started = time.monotonic()
        completed, timed_out = run_captured(
            [
                sys.executable,
                "-c",
                (
                    "import subprocess,sys,time;"
                    "subprocess.Popen([sys.executable,'-c','import time;"
                    "time.sleep(30)']);"
                    "time.sleep(30)"
                ),
            ],
            env=os.environ.copy(),
            timeout_seconds=0.1,
            termination_grace_seconds=0.1,
        )
        self.assertTrue(timed_out)
        self.assertEqual(completed.returncode, 124)
        self.assertLess(time.monotonic() - started, 2)

    def test_keyboard_interrupt_terminates_headless_process_group(self) -> None:
        process = MagicMock()
        process.pid = 12345
        process.communicate.side_effect = [KeyboardInterrupt, ("", "")]
        with (
            patch("process_control.subprocess.Popen", return_value=process),
            patch("process_control.os.killpg") as killpg,
        ):
            with self.assertRaises(CapturedKeyboardInterrupt) as raised:
                run_captured(["fixture"], timeout_seconds=1)
        killpg.assert_called_once_with(12345, signal.SIGTERM)
        self.assertEqual(raised.exception.completed.returncode, 130)

    def test_headless_runtime_preserves_partial_interrupt_output(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["fixture"],
            returncode=130,
            stdout='{"type":"partial"}\n',
            stderr="Interrupted by user.\n",
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trace = root / "trace.jsonl"
            stderr = root / "stderr.txt"
            with patch(
                "eval_runtime.run_captured",
                side_effect=CapturedKeyboardInterrupt(completed),
            ):
                with self.assertRaises(CapturedKeyboardInterrupt):
                    HeadlessEvalRun().run_captured(
                        ["fixture"],
                        cwd=root,
                        env=os.environ.copy(),
                        timeout_seconds=1,
                        pane_role="control",
                        title="fixture",
                        trace_path=trace,
                        stderr_path=stderr,
                    )
            self.assertEqual(trace.read_text(encoding="utf-8"), completed.stdout)
            self.assertEqual(stderr.read_text(encoding="utf-8"), completed.stderr)


class PlanningTests(unittest.TestCase):
    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_default_dry_run_path_is_external_and_not_created(self, _resolve) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            output = default_run_output(skill.name)
            with patch("herdr_runtime.HerdrEvalRun._cli") as cli:
                report = plan_run(
                    skill_path=skill,
                    output_dir=output,
                    model="provider/model-1",
                    trials=3,
                )
            cli.assert_not_called()
            self.assertTrue(Path(report["output_dir"]).is_relative_to(DEFAULT_EVAL_RUNS_ROOT))
            self.assertFalse(output.exists())
            self.assertEqual(
                report["harness_invocations"],
                {
                    "target": 6,
                    "condition_judges": 0,
                    "references": 0,
                    "counter_references": 0,
                    "judge": 0,
                    "total": 6,
                },
            )
            self.assertEqual(report["provider_model_calls"], "unknown")
            self.assertEqual(report["observer"]["kind"], "headless")
            self.assertEqual(
                report["execution_order"]["policy"],
                "counterbalanced_by_trial",
            )

    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_external_output_override_is_preserved(self, _resolve) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            output = root / "custom-run"
            report = plan_run(
                skill_path=skill,
                output_dir=output,
                model="provider/model-1",
                trials=1,
            )
            self.assertEqual(Path(report["output_dir"]), output.resolve())
            self.assertFalse(output.exists())

    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_output_inside_active_skills_is_rejected(self, _resolve) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            with self.assertRaisesRegex(ValueError, "cannot live inside"):
                plan_run(
                    skill_path=skill,
                    output_dir=SKILL_ROOT.parent / "generated-run",
                    model="provider/model-1",
                    trials=1,
                )

    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_output_inside_external_target_skill_is_rejected(self, _resolve) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            with self.assertRaisesRegex(ValueError, "evaluated skill"):
                plan_run(
                    skill_path=skill,
                    output_dir=skill / "generated-run",
                    model="provider/model-1",
                    trials=1,
                )

    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/fake", "1.0"))
    def test_control_fixture_rejects_project_local_target_skill(self, _resolve) -> None:
        for harness, native_root in (
            ("codex", ".agents/skills"),
            ("claude-code", ".claude/skills"),
        ):
            with self.subTest(harness=harness), tempfile.TemporaryDirectory() as temp:
                skill = _make_schema2_skill(Path(temp))
                fixture = skill / "fixtures" / "contaminated"
                hidden_skill = fixture / native_root / skill.name
                hidden_skill.mkdir(parents=True)
                (hidden_skill / "SKILL.md").write_text("# Hidden\n", encoding="utf-8")
                suite_path = skill / "evals" / "evals.json"
                suite = json.loads(suite_path.read_text(encoding="utf-8"))
                suite["evals"][0]["fixture"] = "fixtures/contaminated"
                _write_json(suite_path, suite)
                with self.assertRaisesRegex(ValueError, "control fixture"):
                    plan_run(
                        skill_path=skill,
                        output_dir=Path(temp) / "run",
                        model="provider/model-1",
                        trials=1,
                        harness=harness,
                    )

    @patch("run_skill_eval._run_condition")
    @patch(
        "run_skill_eval._validate_references",
        side_effect=ValueError("reference solution failed"),
    )
    @patch("run_skill_eval.start_eval_run")
    @patch("run_skill_eval.require_observer_environment")
    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_reference_failure_prevents_trials(
        self,
        _resolve,
        _require,
        start,
        _references,
        run_condition,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            fake = _FakeHerdrRun(root / "run")
            start.return_value = fake
            with self.assertRaisesRegex(ValueError, "reference solution failed"):
                run_suite(
                    skill_path=skill,
                    output_dir=root / "run",
                    model="provider/model-1",
                    trials=1,
                    observer="herdr",
                )
            run_condition.assert_not_called()
            self.assertEqual(fake.finishes, ["failed"])

    def test_failed_target_stops_before_model_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite = load_suite(skill)
            case = suite["evals"][0]
            case["_tool_profile"] = suite["tool_profile"]
            case["_activation_mode"] = suite["activation_mode"]
            eval_run = MagicMock()

            def failed_capture(*_args, trace_path, stderr_path, **_kwargs):
                trace_path.write_text('{"model":"provider/model-1"}\n', encoding="utf-8")
                stderr_path.write_text("failed\n", encoding="utf-8")
                return (
                    subprocess.CompletedProcess(["pi"], 1, "", "failed"),
                    False,
                )

            eval_run.run_captured.side_effect = failed_capture
            metadata = {
                "actual_model": "provider/model-1",
                "model_attested": True,
                "session_id": "failed-session",
                "final_response": "partial",
                "skill_injection_attested": False,
                "skill_explicitly_accessed": False,
            }
            with (
                patch("run_skill_eval.trace_metadata", return_value=metadata),
                patch("run_skill_eval._model_graders", return_value=({}, [])) as graders,
                self.assertRaisesRegex(RuntimeError, "target invocation failed"),
            ):
                _run_condition(
                    root=root / "run",
                    skill_path=skill,
                    case=case,
                    suite_root=Path(suite["suite_root"]),
                    trial=1,
                    condition="without_skill",
                    harness="pi",
                    executable="pi",
                    model="provider/model-1",
                    timeout_seconds=1,
                    judge_model="provider/judge-1",
                    judge_timeout_seconds=1,
                    eval_run=eval_run,
                )
            graders.assert_not_called()

    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_herdr_observer_requires_environment_before_creating_output(
        self,
        _resolve,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            output = root / "run"
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "HERDR_ENV=1"):
                    run_suite(
                        skill_path=skill,
                        output_dir=output,
                        model="provider/model-1",
                        trials=1,
                        observer="herdr",
                    )
            self.assertFalse(output.exists())

    @patch("herdr_runtime.HerdrEvalRun._cli")
    @patch("herdr_runtime.HerdrEvalRun.require_environment")
    def test_herdr_workspace_uses_named_retained_2x2_layout(
        self,
        _require,
        cli,
    ) -> None:
        cli.side_effect = [
            {
                "workspace": {"workspace_id": "w1"},
                "root_pane": {"pane_id": "w1:p1"},
            },
            {"pane": {"pane_id": "w1:p2"}},
            {"pane": {"pane_id": "w1:p3"}},
            {"pane": {"pane_id": "w1:p4"}},
            {},
            {},
            {},
            {},
            {},
            {},
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = HerdrEvalRun.start(
                skill_name="fixture-skill",
                output_dir=root / "run-1",
                cwd=root,
            )
            self.assertEqual(run.workspace_id, "w1")
            self.assertEqual(
                run.panes,
                PaneSet(
                    coordinator="w1:p1",
                    control="w1:p3",
                    with_skill="w1:p2",
                    judge_results="w1:p4",
                ),
            )
            calls = [item.args for item in cli.call_args_list]
            self.assertIn(
                (
                    "workspace",
                    "create",
                    "--cwd",
                    str(root),
                    "--label",
                    "eval:fixture-skill:run-1",
                    "--no-focus",
                ),
                calls,
            )
            self.assertIn(
                (
                    "pane",
                    "split",
                    "w1:p2",
                    "--direction",
                    "right",
                    "--ratio",
                    "0.5",
                    "--cwd",
                    str(root),
                    "--no-focus",
                ),
                calls,
            )
            self.assertEqual(calls[-1], ("workspace", "focus", "w1"))

    def test_herdr_job_serializes_only_supported_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = HerdrEvalRun(
                workspace_id="w1",
                workspace_label="eval:test:run",
                panes=PaneSet("w1:p1", "w1:p2", "w1:p3", "w1:p4"),
                output_dir=root,
            )
            run.status_path.parent.mkdir(parents=True)
            run.status_path.write_text("", encoding="utf-8")

            def fake_cli(*args: str) -> dict:
                if args[:3] == ("pane", "run", "w1:p2"):
                    result = root / "herdr" / "jobs" / "0001.result.json"
                    _write_json(
                        result,
                        {
                            "returncode": 0,
                            "timed_out": False,
                            "duration_seconds": 0.01,
                        },
                    )
                return {}

            env = os.environ.copy()
            env["HOME"] = str(root / "isolated-home")
            env["CODEX_HOME"] = str(root / "codex-home")
            with patch.object(run, "_cli", side_effect=fake_cli):
                run.run_captured(
                    ["fixture"],
                    cwd=root,
                    env=env,
                    timeout_seconds=1,
                    pane_role="control",
                    title="fixture",
                    trace_path=root / "trace.jsonl",
                    stderr_path=root / "stderr.txt",
                )
            job = json.loads(
                (root / "herdr/jobs/0001.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                job["env_overrides"],
                {"CODEX_HOME": str(root / "codex-home"), "HOME": str(root / "isolated-home")},
            )

    def test_herdr_worker_applies_serialized_environment_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job_path = root / "job.json"
            trace = root / "trace.jsonl"
            result = root / "result.json"
            expected = str(root / "hermes-config.json")
            _write_json(
                job_path,
                {
                    "command": [
                        sys.executable,
                        "-c",
                        "import json,os; print(json.dumps({'value': os.environ.get('HERMES_CONFIG')}))",
                    ],
                    "cwd": str(root),
                    "trace_path": str(trace),
                    "stderr_path": str(root / "stderr.txt"),
                    "result_path": str(result),
                    "timeout_seconds": 1,
                    "title": "fixture",
                    "env_overrides": {"HERMES_CONFIG": expected},
                },
            )
            self.assertEqual(_run_job(job_path), 0)
            event = json.loads(trace.read_text(encoding="utf-8"))
            self.assertEqual(event["value"], expected)

    @patch("herdr_runtime.HerdrEvalRun._cli", return_value={})
    def test_cancel_targets_only_the_active_eval_pane(self, cli) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = HerdrEvalRun(
                workspace_id="w1",
                workspace_label="eval:test:run",
                panes=PaneSet("w1:p1", "w1:p2", "w1:p3", "w1:p4"),
                output_dir=root,
            )
            run.status_path.parent.mkdir(parents=True)
            run.status_path.write_text("", encoding="utf-8")
            run._active_pane = "w1:p2"
            run.cancel_active()
            cli.assert_any_call("pane", "send-keys", "w1:p2", "ctrl+c")

    @patch("herdr_runtime.HerdrEvalRun._cli", return_value={})
    def test_finish_retains_workspace_and_notifies_once(self, cli) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = HerdrEvalRun(
                workspace_id="w1",
                workspace_label="eval:test:run",
                panes=PaneSet("w1:p1", "w1:p2", "w1:p3", "w1:p4"),
                output_dir=root,
            )
            run.status_path.parent.mkdir(parents=True)
            run.status_path.write_text("", encoding="utf-8")
            run.finish(
                status="completed",
                summary="Verdict: improved",
                artifact_path=root,
            )
            calls = [item.args for item in cli.call_args_list]
            self.assertIn(
                ("workspace", "rename", "w1", "[completed] eval:test:run"),
                calls,
            )
            notifications = [
                call for call in calls if call[:2] == ("notification", "show")
            ]
            self.assertEqual(len(notifications), 1)
            self.assertFalse(
                any(call[:2] == ("workspace", "close") for call in calls)
            )

    def test_cancellation_marks_partial_run_invalid_and_retains_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            output = root / "run"
            fake = _InterruptHerdrRun(output)
            with (
                patch("run_skill_eval.require_observer_environment"),
                patch("run_skill_eval.start_eval_run", return_value=fake),
                patch(
                    "run_skill_eval.resolve_harness",
                    return_value=("/usr/local/bin/pi", "1.0"),
                ),
            ):
                with self.assertRaises(KeyboardInterrupt):
                    run_suite(
                        skill_path=skill,
                        output_dir=output,
                        model="provider/model-1",
                        trials=1,
                        observer="herdr",
                    )
            state = json.loads(
                (output / "run_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(state["status"], "cancelled")
            self.assertFalse(state["valid"])
            self.assertEqual(state["completed_conditions"], 0)
            self.assertEqual(fake.finishes, ["cancelled"])
            self.assertTrue(output.is_dir())


class EndToEndTests(unittest.TestCase):
    def test_forced_codex_treatment_requires_explicit_skill_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            fake = root / "fake-codex"
            counter = root / "fake-codex.count"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 1.0")
    raise SystemExit(0)

counter = Path(sys.argv[0]).with_suffix(".count")
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
treatment = "$fixture-skill" in " ".join(sys.argv)
rollout = (
    Path(os.environ["CODEX_HOME"])
    / "sessions/2026/08/02/rollout-fixture-session.jsonl"
)
rollout.parent.mkdir(parents=True, exist_ok=True)
rollout.write_text(
    "\\n".join(json.dumps(event) for event in [
        {"type": "turn_context", "payload": {"model": "provider/model-1"}},
        {
            "type": "world_state",
            "payload": {
                "state": {
                    "host_skills": {
                        "body": (
                            "- fixture-skill: (file: "
                            "/tmp/fixture-skill/SKILL.md)"
                            if treatment
                            else ""
                        )
                    }
                }
            },
        },
    ]) + "\\n",
    encoding="utf-8",
)
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/model-1",
    "session_id": "fixture-session",
    "skills": ["fixture-skill"] if treatment else [],
}))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/model-1",
        "content": [{"type": "text", "text": "done"}],
    },
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.assertRaisesRegex(
                RuntimeError,
                "forced target skill fixture-skill was not explicitly accessed",
            ):
                run_suite(
                    skill_path=skill,
                    output_dir=root / "run",
                    model="provider/model-1",
                    trials=1,
                    harness="codex",
                    harness_bin=str(fake),
                )
            self.assertEqual(counter.read_text(encoding="utf-8"), "2")

    def test_missing_judge_attestation_stops_after_first_paid_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "Judge completion",
                    "type": "model_rubric",
                    "rubric": "The response completes the task.",
                }
            ]
            _write_json(suite_path, suite)
            fake = root / "fake-codex"
            counter = root / "fake-codex.count"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 1.0")
    raise SystemExit(0)

counter = Path(sys.argv[0]).with_suffix(".count")
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
joined = " ".join(sys.argv)
is_judge = "You are grading one agent response." in joined
response = (
    '{"passed": true, "reason": "fixture passes"}'
    if is_judge
    else "done"
)
model = "provider/judge-1" if is_judge else "provider/model-1"
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": model,
    "session_id": "missing-rollout",
}))
print(json.dumps({"type": "thread.started", "thread_id": "missing-model"}))
print(json.dumps({
    "type": "item.completed",
    "item": {"type": "agent_message", "text": response},
}))
print(json.dumps({
    "type": "turn.completed",
    "usage": {"input_tokens": 1, "output_tokens": 1},
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.assertRaisesRegex(
                RuntimeError,
                "judge model provider/judge-1 was not attested",
            ):
                run_suite(
                    skill_path=skill,
                    output_dir=root / "run",
                    model="provider/model-1",
                    trials=1,
                    harness="codex",
                    harness_bin=str(fake),
                    judge_model="provider/judge-1",
                )
            self.assertEqual(counter.read_text(encoding="utf-8"), "1")

    def test_missing_target_attestation_stops_after_first_paid_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            fake = root / "fake-codex"
            counter = root / "fake-codex.count"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 1.0")
    raise SystemExit(0)

counter = Path(sys.argv[0]).with_suffix(".count")
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/model-1",
    "session_id": "missing-rollout",
}))
print(json.dumps({"type": "thread.started", "thread_id": "missing-model"}))
print(json.dumps({
    "type": "item.completed",
    "item": {"type": "agent_message", "text": "done"},
}))
print(json.dumps({
    "type": "turn.completed",
    "usage": {"input_tokens": 1, "output_tokens": 1},
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.assertRaisesRegex(
                RuntimeError,
                "target model provider/model-1 was not attested",
            ):
                run_suite(
                    skill_path=skill,
                    output_dir=root / "run",
                    model="provider/model-1",
                    trials=1,
                    harness="codex",
                    harness_bin=str(fake),
                )
            self.assertEqual(counter.read_text(encoding="utf-8"), "1")

    def test_wrong_judge_model_stops_after_first_paid_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "Judge completion",
                    "type": "model_rubric",
                    "rubric": "The response completes the task.",
                }
            ]
            _write_json(suite_path, suite)
            fake = root / "fake-codex"
            counter = root / "fake-codex.count"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 1.0")
    raise SystemExit(0)

counter = Path(sys.argv[0]).with_suffix(".count")
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
rollout = (
    Path(os.environ["CODEX_HOME"])
    / "sessions/2026/08/02/rollout-wrong-model.jsonl"
)
rollout.parent.mkdir(parents=True, exist_ok=True)
rollout.write_text(
    json.dumps({
        "type": "turn_context",
        "payload": {"model": "provider/wrong-model"},
    }) + "\\n",
    encoding="utf-8",
)
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/wrong-model",
    "session_id": "wrong-model",
}))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/wrong-model",
        "content": [{
            "type": "text",
            "text": '{"passed": true, "reason": "fixture passes"}',
        }],
    },
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.assertRaisesRegex(
                RuntimeError,
                "requested judge model provider/judge-1 but attested provider/wrong-model",
            ):
                run_suite(
                    skill_path=skill,
                    output_dir=root / "run",
                    model="provider/model-1",
                    trials=1,
                    harness="codex",
                    harness_bin=str(fake),
                    judge_model="provider/judge-1",
                )
            self.assertEqual(counter.read_text(encoding="utf-8"), "1")

    def test_wrong_target_model_stops_after_first_paid_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            fake = root / "fake-codex"
            counter = root / "fake-codex.count"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 1.0")
    raise SystemExit(0)

counter = Path(sys.argv[0]).with_suffix(".count")
count = int(counter.read_text()) + 1 if counter.exists() else 1
counter.write_text(str(count))
rollout = (
    Path(os.environ["CODEX_HOME"])
    / "sessions/2026/08/02/rollout-wrong-model.jsonl"
)
rollout.parent.mkdir(parents=True, exist_ok=True)
rollout.write_text(
    json.dumps({
        "type": "turn_context",
        "payload": {"model": "provider/wrong-model"},
    }) + "\\n",
    encoding="utf-8",
)
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/wrong-model",
    "session_id": "wrong-model",
}))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/wrong-model",
        "content": [{"type": "text", "text": "done"}],
    },
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            with self.assertRaisesRegex(
                RuntimeError,
                "requested target model provider/model-1 but attested provider/wrong-model",
            ):
                run_suite(
                    skill_path=skill,
                    output_dir=root / "run",
                    model="provider/model-1",
                    trials=1,
                    harness="codex",
                    harness_bin=str(fake),
                )
            self.assertEqual(counter.read_text(encoding="utf-8"), "1")

    def test_codex_run_hashes_persisted_runtime_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "Judge completion",
                    "type": "model_rubric",
                    "rubric": "The response completes the task.",
                }
            ]
            suite["evals"][0]["reference"]["response"] = "PASS"
            _write_json(suite_path, suite)
            fake = root / "fake-codex"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-codex 1.0")
    raise SystemExit(0)

joined = " ".join(sys.argv)
treatment = "$fixture-skill" in joined
is_judge = "You are grading one agent response." in joined
model = sys.argv[sys.argv.index("--model") + 1]
thread_id = "fixture-thread"
rollout = (
    Path(os.environ["CODEX_HOME"])
    / "sessions/2026/08/02/rollout-fixture-thread.jsonl"
)
rollout.parent.mkdir(parents=True, exist_ok=True)
events = [
    {"type": "turn_context", "payload": {"model": model}},
    {
        "type": "world_state",
        "payload": {
            "state": {
                "host_skills": {
                    "body": (
                        "- fixture-skill: (file: "
                        "/tmp/fixture-skill/SKILL.md)"
                        if treatment
                        else ""
                    )
                }
            }
        },
    },
]
if treatment:
    installed = Path.cwd() / ".agents/skills/fixture-skill/SKILL.md"
    events.append({
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "content": [{
                "type": "input_text",
                "text": (
                    "<skill>\\n<name>fixture-skill</name>\\n"
                    f"<path>{installed}</path>\\n</skill>"
                ),
            }],
        },
    })
rollout.write_text(
    "\\n".join(json.dumps(event) for event in events) + "\\n",
    encoding="utf-8",
)
print(json.dumps({"type": "thread.started", "thread_id": thread_id}))
print(json.dumps({
    "type": "item.completed",
    "item": {
        "type": "agent_message",
        "text": (
            '{"passed": true, "reason": "fixture passes"}'
            if is_judge
            else "PASS" if treatment else "FAIL"
        ),
    },
}))
print(json.dumps({
    "type": "turn.completed",
    "usage": {"input_tokens": 1, "output_tokens": 1},
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            output = root / "run-codex-attested"
            report = run_suite(
                skill_path=skill,
                output_dir=output,
                model="provider/model-1",
                trials=1,
                harness="codex",
                harness_bin=str(fake),
                judge_model="provider/judge-1",
            )
            self.assertTrue(report["valid"])
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            treatment_record = manifest["trials"][0]["conditions"]["with_skill"]
            self.assertEqual(treatment_record["actual_model"], "provider/model-1")
            self.assertTrue(treatment_record["model_attested"])
            self.assertRegex(
                treatment_record["attestation_trace_sha256"],
                r"^[0-9a-f]{64}$",
            )
            judge_record = treatment_record["judge_records"][0]
            self.assertEqual(judge_record["actual_model"], "provider/judge-1")
            self.assertRegex(
                judge_record["attestation_trace_sha256"],
                r"^[0-9a-f]{64}$",
            )
            reference_judge = manifest["reference_validation"][0][
                "judge_records"
            ][0]
            reference_attestation = (
                output / reference_judge["attestation_trace_path"]
            )
            original_reference_attestation = reference_attestation.read_text(
                encoding="utf-8"
            )
            reference_attestation.write_text(
                original_reference_attestation.replace(
                    "provider/judge-1",
                    "provider/judge-other",
                ),
                encoding="utf-8",
            )
            reference_judge["attestation_trace_sha256"] = _sha256(
                reference_attestation
            )
            _write_json(output / "run_manifest.json", manifest)
            mismatched_reference = aggregate(output)
            self.assertFalse(mismatched_reference["valid"])
            self.assertTrue(
                any(
                    "judge_model_mismatch" in reason
                    for reason in mismatched_reference["invalid_reasons"]
                )
            )
            reference_attestation.write_text(
                original_reference_attestation,
                encoding="utf-8",
            )
            reference_judge["attestation_trace_sha256"] = _sha256(
                reference_attestation
            )
            saved_attestation_path = treatment_record["attestation_trace_path"]
            saved_attestation_sha = treatment_record["attestation_trace_sha256"]
            treatment_record["attestation_trace_path"] = ""
            treatment_record["attestation_trace_sha256"] = ""
            _write_json(output / "run_manifest.json", manifest)
            missing_attestation = aggregate(output)
            self.assertFalse(missing_attestation["valid"])
            self.assertTrue(
                any(
                    "attestation_trace_missing" in reason
                    for reason in missing_attestation["invalid_reasons"]
                )
            )
            treatment_record["attestation_trace_path"] = saved_attestation_path
            treatment_record["attestation_trace_sha256"] = saved_attestation_sha
            treatment_record["skill_injection_attested"] = False
            treatment_record["skill_explicitly_accessed"] = False
            _write_json(output / "run_manifest.json", manifest)
            reaggregated = aggregate(output)
            self.assertTrue(reaggregated["runtime_attestation_complete"])
            self.assertEqual(reaggregated["routing"]["explicit_accesses"], 1)
            judge_attestation = output / judge_record["attestation_trace_path"]
            original_judge_attestation = judge_attestation.read_text(
                encoding="utf-8"
            )
            judge_attestation.write_text(
                original_judge_attestation.replace(
                    "provider/judge-1",
                    "provider/judge-other",
                ),
                encoding="utf-8",
            )
            judge_record["attestation_trace_sha256"] = _sha256(
                judge_attestation
            )
            _write_json(output / "run_manifest.json", manifest)
            mismatched_judge = aggregate(output)
            self.assertFalse(mismatched_judge["valid"])
            self.assertTrue(
                any(
                    "judge_model_mismatch" in reason
                    for reason in mismatched_judge["invalid_reasons"]
                )
            )
            judge_attestation.write_text(
                original_judge_attestation,
                encoding="utf-8",
            )
            judge_record["attestation_trace_sha256"] = _sha256(
                judge_attestation
            )
            attestation_trace = output / treatment_record["attestation_trace_path"]
            attestation_trace.write_text(
                attestation_trace.read_text(encoding="utf-8").replace(
                    "provider/model-1",
                    "provider/model-other",
                ),
                encoding="utf-8",
            )
            treatment_record["attestation_trace_sha256"] = _sha256(
                attestation_trace
            )
            _write_json(output / "run_manifest.json", manifest)
            mismatched = aggregate(output)
            self.assertFalse(mismatched["valid"])
            self.assertTrue(
                any(
                    "model_mismatch" in reason
                    for reason in mismatched["invalid_reasons"]
                )
            )
            attestation_trace.write_text(
                attestation_trace.read_text(encoding="utf-8") + "{}\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "attestation_trace_sha256"):
                aggregate(output)

    def test_fake_runs_complete_for_every_selected_harness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"][0]["value"] = "PASS"
            suite["evals"][0]["reference"]["response"] = "PASS"
            _write_json(suite_path, suite)
            fake = root / "fake-harness"
            fake.write_text(
                """#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

if "--version" in sys.argv:
    print("fake-harness 1.0")
    raise SystemExit(0)

joined = " ".join(sys.argv)
treatment = (
    "--skill " in joined
    or "--skills " in joined
    or "/fixture-skill" in joined
    or "$fixture-skill" in joined
)
if "CODEX_HOME" in os.environ:
    rollout = (
        Path(os.environ["CODEX_HOME"])
        / "sessions/2026/08/02/rollout-fixture-session.jsonl"
    )
    rollout.parent.mkdir(parents=True, exist_ok=True)
    events = [
        {"type": "turn_context", "payload": {"model": "provider/model-1"}},
    ]
    if treatment:
        installed = Path.cwd() / ".agents/skills/fixture-skill/SKILL.md"
        events.append({
            "type": "response_item",
            "payload": {
                "type": "message",
                "role": "user",
                "content": [{
                    "type": "input_text",
                    "text": (
                        "<skill>\\n<name>fixture-skill</name>\\n"
                        f"<path>{installed}</path>\\n</skill>"
                    ),
                }],
            },
        })
    rollout.write_text(
        "\\n".join(json.dumps(event) for event in events) + "\\n",
        encoding="utf-8",
    )
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/model-1",
    "session_id": "fixture-session",
    "skills": ["fixture-skill"] if treatment else [],
}))
if treatment:
    print(json.dumps({
        "name": "skill",
        "arguments": {"skill": "fixture-skill"},
    }))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/model-1",
        "content": [{"type": "text", "text": "PASS" if treatment else "FAIL"}],
        "usage": {"input": 1, "output": 1, "totalTokens": 2},
    }
}))
""",
                encoding="utf-8",
            )
            fake.chmod(0o755)
            for harness in HARNESS_NAMES:
                with self.subTest(harness=harness):
                    report = run_suite(
                        skill_path=skill,
                        output_dir=root / f"run-{harness}",
                        model="provider/model-1",
                        trials=1,
                        harness=harness,
                        harness_bin=str(fake),
                    )
                    self.assertEqual(report["verdict"], "improved")

    def test_fake_pi_run_writes_a_valid_paired_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"][0]["value"] = "PASS"
            suite["evals"][0]["reference"]["response"] = "PASS"
            _write_json(suite_path, suite)
            fake_pi = root / "fake-pi"
            fake_pi.write_text(
                """#!/usr/bin/env python3
import json
import sys

if "--version" in sys.argv:
    print("fake-pi 1.0")
    raise SystemExit(0)

treatment = "--skill" in sys.argv
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/model-1",
    "session_id": "fixture-session",
    "skills": ["fixture-skill"] if treatment else [],
}))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/model-1",
        "content": [{"type": "text", "text": "PASS" if treatment else "FAIL"}],
        "usage": {"input": 1, "output": 1, "totalTokens": 2},
    }
}))
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            output = root / "run"
            report = run_suite(
                skill_path=skill,
                output_dir=output,
                model="provider/model-1",
                trials=2,
                pi_bin=str(fake_pi),
            )
            self.assertTrue(report["valid"])
            self.assertEqual(report["verdict"], "improved")
            self.assertTrue(report["mechanism_valid"])
            self.assertTrue((output / "run_manifest.json").is_file())
            self.assertTrue((output / "benchmark.json").is_file())
            state = json.loads((output / "run_state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["observer"], "headless")
            manifest = json.loads(
                (output / "run_manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["execution_schedule"],
                [
                    {
                        "case_id": "case",
                        "trial": 1,
                        "conditions": ["without_skill", "with_skill"],
                    },
                    {
                        "case_id": "case",
                        "trial": 2,
                        "conditions": ["with_skill", "without_skill"],
                    },
                ],
            )

    def test_model_judges_share_the_visible_judge_results_pane(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = _make_schema2_skill(root)
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["evals"][0]["graders"] = [
                {
                    "name": "Judge completion",
                    "type": "model_rubric",
                    "rubric": "The response completes the task.",
                }
            ]
            _write_json(suite_path, suite)
            fake_pi = root / "fake-pi"
            fake_pi.write_text(
                """#!/usr/bin/env python3
import json
import sys

if "--version" in sys.argv:
    print("fake-pi 1.0")
    raise SystemExit(0)

prompt = sys.argv[-1]
treatment = "--skill" in sys.argv
if prompt.startswith("You are grading one agent response."):
    response = '{"passed": true, "reason": "fixture passes"}'
else:
    response = "done"
print(json.dumps({
    "type": "system",
    "subtype": "init",
    "model": "provider/model-1",
    "session_id": "fixture-session",
    "skills": ["fixture-skill"] if treatment else [],
}))
print(json.dumps({
    "message": {
        "role": "assistant",
        "model": "provider/model-1",
        "content": [{"type": "text", "text": response}],
        "usage": {"input": 1, "output": 1, "totalTokens": 2},
    }
}))
""",
                encoding="utf-8",
            )
            fake_pi.chmod(0o755)
            output = root / "run"
            fake_herdr = _FakeHerdrRun(output)
            with (
                patch("run_skill_eval.require_observer_environment"),
                patch(
                    "run_skill_eval.start_eval_run",
                    return_value=fake_herdr,
                ),
            ):
                report = run_suite(
                    skill_path=skill,
                    output_dir=output,
                    model="provider/model-1",
                    trials=1,
                    pi_bin=str(fake_pi),
                    judge_model="provider/model-1",
                    observer="herdr",
                )
            self.assertTrue(report["valid"])
            self.assertEqual(
                fake_herdr.roles,
                [
                    "judge_results",
                    "control",
                    "judge_results",
                    "with_skill",
                    "judge_results",
                ],
            )

    def test_condition_order_is_counterbalanced_in_the_manifest(self) -> None:
        self.assertEqual(
            condition_order(1),
            ("without_skill", "with_skill"),
        )
        self.assertEqual(
            condition_order(2),
            ("with_skill", "without_skill"),
        )

    @patch("run_skill_eval.resolve_harness", return_value=("/usr/local/bin/pi", "1.0"))
    def test_dry_run_counts_multiple_graders_and_subset_counters(self, _resolve) -> None:
        with tempfile.TemporaryDirectory() as temp:
            skill = _make_schema2_skill(Path(temp))
            suite_path = skill / "evals" / "evals.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            first = suite["evals"][0]
            first["graders"] = [
                {"name": "model one", "type": "model_rubric", "rubric": "done"},
                {"name": "model two", "type": "model_rubric", "rubric": "done"},
            ]
            second = dict(first)
            second["id"] = "second"
            second["graders"] = [
                {"name": "model three", "type": "model_rubric", "rubric": "done"},
            ]
            second["counter_reference"] = {"response": "wrong"}
            third = dict(first)
            third["id"] = "third"
            third["graders"] = [
                {"name": "Returns done", "type": "response_contains", "value": "done"},
            ]
            third["counter_reference"] = {"response": "wrong"}
            suite["evals"] = [first, second, third]
            _write_json(suite_path, suite)
            report = plan_run(
                skill_path=skill,
                output_dir=Path(temp) / "run",
                model="provider/model-1",
                judge_model="provider/judge-1",
                trials=3,
            )
            self.assertEqual(report["harness_invocations"]["total"], 40)


class AggregateTests(unittest.TestCase):
    def _accounting_snapshot(self, root: Path, *, graders: int, counter: bool) -> None:
        snapshot_path = root / "suite_snapshot.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        snapshot["cases"][0].update(
            {
                "model_rubric_count": graders,
                "counter_reference_declared": counter,
            }
        )
        _write_json(snapshot_path, snapshot)
        manifest_path = root / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["suite_sha256"] = _sha256(snapshot_path)
        reference = {
            "case_id": "case",
            "valid": True,
            "grading": _grading(True),
            "judge_records": [],
        }
        if counter:
            reference["counter_reference"] = {
                "grading": _grading(False),
                "judge_records": [],
            }
        manifest["reference_validation"] = [reference]
        _write_json(manifest_path, manifest)

    def test_undeclared_grader_discrimination_remains_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            report = aggregate(root)
            self.assertEqual(
                report["grader_discrimination"],
                {"claim": "none", "validated": False},
            )
            self.assertTrue(
                any(
                    "optional counters do not prove every" in limit
                    for limit in report["limits"]
                )
            )

    def test_no_judge_calls_have_zero_usage_only_when_zero_are_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=False)
            operations = aggregate(root)["operations"]
            self.assertEqual(operations["condition_judges"]["tokens"], 0)
            self.assertEqual(operations["references"]["cost"], 0.0)
            self.assertEqual(operations["full"]["tokens"], 20)
            self.assertEqual(
                operations["full"]["tokens_coverage"],
                {"reported": 2, "expected": 2},
            )

    def test_unexpected_usage_when_zero_expected_is_not_reported_as_zero(self) -> None:
        bucket = _usage_bucket(
            [{"total_tokens": 7, "cost": 0.07}],
            expected=0,
        )
        self.assertIsNone(bucket["tokens"])
        self.assertIsNone(bucket["cost"])
        self.assertEqual(
            bucket["tokens_coverage"],
            {"reported": 1, "expected": 0},
        )
        boolean_cost = _usage_bucket(
            [{"total_tokens": 0, "cost": True}],
            expected=1,
        )
        self.assertIsNone(boolean_cost["cost"])
        self.assertEqual(
            boolean_cost["cost_coverage"],
            {"reported": 0, "expected": 1},
        )

    def test_accounting_snapshot_requires_complete_unique_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=False)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for references, message in (
                ([], "complete suite case set"),
                (
                    [
                        {
                            "case_id": "case",
                            "valid": True,
                            "grading": _grading(True),
                            "judge_records": [],
                        },
                        {
                            "case_id": "case",
                            "valid": True,
                            "grading": _grading(True),
                            "judge_records": [],
                        },
                    ],
                    "duplicate case_id",
                ),
            ):
                with self.subTest(references=references):
                    manifest["reference_validation"] = references
                    _write_json(manifest_path, manifest)
                    with self.assertRaisesRegex(ValueError, message):
                        aggregate(root)

    def test_counter_presence_must_match_accounting_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=True)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["reference_validation"] = [
                {
                    "case_id": "case",
                    "valid": True,
                    "grading": _grading(True),
                    "judge_records": [],
                }
            ]
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "counter_reference does not match"):
                aggregate(root)

    def test_declared_counter_reference_must_be_an_object(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=True)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["reference_validation"][0]["counter_reference"] = None
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "counter_reference must be an object"):
                aggregate(root)

    def test_counter_reference_must_retain_a_failing_grading(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=True)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["reference_validation"][0]["counter_reference"]["grading"] = (
                _grading(True)
            )
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "counter_reference passed"):
                aggregate(root)

    def test_counter_reference_must_fail_every_response_grader(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=True)
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["grader_discrimination"] = "case_contrast"
            snapshot["cases"][0]["response_sensitive_graders"] = [
                {"name": "Rejects the bad structure", "type": "response_regex"},
                {
                    "name": "Judge rejects the bad answer",
                    "type": "response_contains",
                },
            ]
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(snapshot_path)
            manifest["reference_validation"][0]["grading"] = {
                "grader": {"kind": "deterministic_mixed", "schema_version": 2},
                "expectations": [
                    {
                        "text": "Rejects the bad structure",
                        "passed": True,
                        "evidence": "fixture",
                        "grader": "response_regex",
                    },
                    {
                        "text": "Judge rejects the bad answer",
                        "passed": True,
                        "evidence": "fixture",
                        "grader": "response_contains",
                    },
                ],
                "summary": {
                    "passed": 2,
                    "failed": 0,
                    "total": 2,
                    "pass_rate": 1.0,
                },
            }
            manifest["reference_validation"][0]["counter_reference"][
                "grading"
            ] = {
                "grader": {"kind": "deterministic_mixed", "schema_version": 2},
                "expectations": [
                    {
                        "text": "Rejects the bad structure",
                        "passed": False,
                        "evidence": "fixture",
                        "grader": "response_regex",
                    },
                    {
                        "text": "Judge rejects the bad answer",
                        "passed": True,
                        "evidence": "fixture",
                        "grader": "response_contains",
                    },
                ],
                "summary": {
                    "passed": 1,
                    "failed": 1,
                    "total": 2,
                    "pass_rate": 0.5,
                },
            }
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(
                ValueError,
                "counter_reference did not fail response-sensitive graders: "
                "Judge rejects the bad answer",
            ):
                aggregate(root)

    def test_case_contrast_requires_complete_snapshot_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=True)
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["grader_discrimination"] = "case_contrast"
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(snapshot_path)
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(
                ValueError,
                "response_sensitive_graders must be a list",
            ):
                aggregate(root)

    def test_case_contrast_requires_a_counter_for_response_graders(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=False)
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["grader_discrimination"] = "case_contrast"
            snapshot["cases"][0]["response_sensitive_graders"] = [
                {"name": "Completes the task", "type": "response_contains"}
            ]
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(snapshot_path)
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(
                ValueError,
                "counter_reference_declared must match response-sensitive graders",
            ):
                aggregate(root)

    def test_case_contrast_revalidates_each_named_grader(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=True)
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["grader_discrimination"] = "case_contrast"
            snapshot["cases"][0]["response_sensitive_graders"] = [
                {"name": "Completes the task", "type": "response_contains"}
            ]
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(snapshot_path)
            _write_json(manifest_path, manifest)
            report = aggregate(root)
            self.assertEqual(
                report["grader_discrimination"],
                {"claim": "case_contrast", "validated": True},
            )

            manifest["reference_validation"][0]["counter_reference"]["grading"][
                "expectations"
            ][0]["grader"] = "response_regex"
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(
                ValueError,
                "counter_reference.grading does not retain the declared "
                "response-sensitive grader outcomes",
            ):
                aggregate(root)

    def test_partial_accounting_metadata_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=0, counter=False)
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            del snapshot["cases"][0]["counter_reference_declared"]
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(snapshot_path)
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "metadata must be complete"):
                aggregate(root)

    def test_condition_judges_cannot_be_shifted_between_cases(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            snapshot_path = root / "suite_snapshot.json"
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            snapshot["cases"] = [
                {
                    "id": "case",
                    "model_rubric_count": 1,
                    "counter_reference_declared": False,
                },
                {
                    "id": "case-2",
                    "model_rubric_count": 1,
                    "counter_reference_declared": False,
                },
            ]
            _write_json(snapshot_path, snapshot)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            original_pair = manifest["trials"][0]
            second_pair = json.loads(json.dumps(original_pair))
            second_pair["case_id"] = "case-2"
            for condition in ("without_skill", "with_skill"):
                second_pair["conditions"][condition]["case_id"] = "case-2"
            manifest.update(
                {
                    "suite_sha256": _sha256(snapshot_path),
                    "case_count": 2,
                    "pair_count": 2,
                    "judge_model": "provider/model-1",
                    "trials": [original_pair, second_pair],
                    "reference_validation": [
                        {
                            "case_id": "case",
                            "valid": True,
                            "grading": _grading(True),
                            "judge_records": [
                                _make_judge_record(
                                    root,
                                    name="reference-one",
                                    model="provider/model-1",
                                )
                            ],
                        },
                        {
                            "case_id": "case-2",
                            "valid": True,
                            "grading": _grading(True),
                            "judge_records": [
                                _make_judge_record(
                                    root,
                                    name="reference-two",
                                    model="provider/model-1",
                                )
                            ],
                        },
                    ],
                }
            )
            original_pair["conditions"]["without_skill"]["judge_records"] = [
                _make_judge_record(root, name="extra-one", model="provider/model-1"),
                _make_judge_record(root, name="extra-two", model="provider/model-1"),
            ]
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "does not match the case model"):
                aggregate(root)

    def test_complete_full_usage_includes_target_and_all_judges(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=1, counter=False)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["judge_model"] = "provider/model-1"
            trial = manifest["trials"][0]["conditions"]
            trial["without_skill"]["judge_records"] = [
                _make_judge_record(root, name="without", model="provider/model-1")
            ]
            trial["with_skill"]["judge_records"] = [
                _make_judge_record(root, name="with", model="provider/model-1")
            ]
            manifest["reference_validation"] = [
                {
                    "case_id": "case",
                    "valid": True,
                    "grading": _grading(True),
                    "judge_records": [
                        _make_judge_record(root, name="reference", model="provider/model-1")
                    ],
                }
            ]
            _write_json(manifest_path, manifest)
            operations = aggregate(root)["operations"]
            self.assertEqual(operations["condition_judges"]["tokens"], 4)
            self.assertEqual(operations["references"]["cost"], 0.02)
            self.assertEqual(operations["full"]["tokens"], 26)
            self.assertEqual(operations["full"]["cost"], 0.08)
            self.assertEqual(
                operations["full"]["tokens_coverage"],
                {"reported": 5, "expected": 5},
            )

    def test_missing_target_or_judge_usage_is_null_with_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            self._accounting_snapshot(root, graders=1, counter=False)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["judge_model"] = "provider/model-1"
            for condition in ("without_skill", "with_skill"):
                judge = _make_judge_record(
                    root,
                    name=f"missing-{condition}",
                    model="provider/model-1",
                )
                judge["total_tokens"] = None
                judge["cost"] = None
                manifest["trials"][0]["conditions"][condition]["judge_records"] = [
                    judge
                ]
            reference_judge = _make_judge_record(
                root,
                name="missing-reference",
                model="provider/model-1",
            )
            reference_judge["total_tokens"] = None
            reference_judge["cost"] = None
            manifest["reference_validation"][0]["judge_records"] = [reference_judge]
            manifest["trials"][0]["conditions"]["without_skill"]["total_tokens"] = None
            manifest["trials"][0]["conditions"]["without_skill"]["cost"] = None
            _write_json(manifest_path, manifest)
            operations = aggregate(root)["operations"]
            self.assertIsNone(operations["without_skill"]["tokens"])
            self.assertEqual(
                operations["without_skill"]["tokens_coverage"],
                {"reported": 0, "expected": 1},
            )
            self.assertIsNone(operations["condition_judges"]["tokens"])
            self.assertEqual(
                operations["condition_judges"]["tokens_coverage"],
                {"reported": 0, "expected": 2},
            )
            self.assertIsNone(operations["full"]["tokens"])

    def test_legacy_snapshot_keeps_target_usage_and_marks_new_buckets_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            operations = aggregate(root)["operations"]
            self.assertEqual(operations["without_skill"]["tokens"], 10)
            self.assertEqual(
                operations["condition_judges"]["tokens_coverage"],
                {"reported": None, "expected": None},
            )
            self.assertIsNone(operations["full"]["tokens"])

    def test_paired_outcomes_produce_descriptive_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True), (True, True), (False, False)])
            report = aggregate(root)
            self.assertTrue(report["valid"])
            self.assertEqual(report["verdict"], "improved")
            self.assertEqual(report["task_success"]["delta"], 0.333)
            self.assertEqual(report["task_success"]["pair_outcomes"]["improved"], 1)

    def test_missing_runtime_attestation_is_separate_from_treatment_validity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            treatment = manifest["trials"][0]["conditions"]["with_skill"]
            trace = root / treatment["trace_path"]
            event = json.loads(trace.read_text(encoding="utf-8"))
            event["skills"] = []
            trace.write_text(json.dumps(event) + "\n", encoding="utf-8")
            treatment["trace_sha256"] = _sha256(trace)
            _write_json(manifest_path, manifest)
            report = aggregate(root)
            self.assertTrue(report["artifact_valid"])
            self.assertTrue(report["mechanism_valid"])
            self.assertFalse(report["runtime_attestation_complete"])
            self.assertEqual(report["outcome_verdict"], "improved")
            self.assertEqual(report["verdict"], "improved")

    def test_trace_visible_control_use_blocks_mechanism_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            control = manifest["trials"][0]["conditions"]["without_skill"]
            trace = root / control["trace_path"]
            event = json.loads(trace.read_text(encoding="utf-8"))
            event["skills"] = ["candidate"]
            trace.write_text(json.dumps(event) + "\n", encoding="utf-8")
            control["trace_sha256"] = _sha256(trace)
            _write_json(manifest_path, manifest)
            report = aggregate(root)
            self.assertTrue(report["artifact_valid"])
            self.assertFalse(report["mechanism_valid"])
            self.assertEqual(report["outcome_verdict"], "improved")
            self.assertEqual(report["verdict"], "mechanism_unconfirmed")

    def test_unforced_treatment_blocks_mechanism_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            treatment = manifest["trials"][0]["conditions"]["with_skill"]
            treatment["skill_activation"] = "available_only"
            _write_json(manifest_path, manifest)
            report = aggregate(root)
            self.assertTrue(report["artifact_valid"])
            self.assertFalse(report["mechanism_valid"])
            self.assertEqual(
                report["mechanism_gaps"],
                ["case/trial-001: treatment_skill_not_forced"],
            )
            self.assertEqual(report["verdict"], "mechanism_unconfirmed")

    def test_autonomous_access_is_scored_as_a_routing_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["activation_mode"] = "autonomous"
            treatment = manifest["trials"][0]["conditions"]["with_skill"]
            treatment["skill_activation"] = "available_for_autonomous_selection"
            trace = root / treatment["trace_path"]
            trace.write_text(
                trace.read_text(encoding="utf-8")
                + json.dumps(
                    {"name": "skill", "arguments": {"skill": "candidate"}}
                )
                + "\n",
                encoding="utf-8",
            )
            treatment["trace_sha256"] = _sha256(trace)
            _write_json(manifest_path, manifest)
            report = aggregate(root)
            self.assertTrue(report["mechanism_valid"])
            self.assertEqual(report["selection_verdict"], "passed")
            self.assertEqual(report["routing"]["accuracy"], 1.0)
            self.assertEqual(report["routing"]["decisions_correct"], 1)

    def test_artifact_hash_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            trace = (
                root
                / "eval-case"
                / "trial-001"
                / "with_skill"
                / "outputs"
                / "trace.jsonl"
            )
            trace.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                aggregate(root)

    def test_non_codex_trace_is_reparsed_during_aggregation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            control = manifest["trials"][0]["conditions"]["without_skill"]
            trace = root / control["trace_path"]
            trace.write_text(
                json.dumps(
                    {
                        "type": "system",
                        "subtype": "init",
                        "model": "provider/wrong-model",
                        "session_id": "tampered",
                        "skills": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            control["trace_sha256"] = _sha256(trace)
            _write_json(manifest_path, manifest)
            report = aggregate(root)
            self.assertFalse(report["valid"])
            self.assertTrue(
                any("model_mismatch" in reason for reason in report["invalid_reasons"])
            )

    def test_aggregation_requires_complete_case_trial_matrix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True), (False, True)])
            suite_path = root / "suite_snapshot.json"
            suite = json.loads(suite_path.read_text(encoding="utf-8"))
            suite["cases"] = [{"id": "case"}]
            _write_json(suite_path, suite)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["suite_sha256"] = _sha256(suite_path)
            manifest["case_count"] = 1
            manifest["trials_per_case"] = 2
            manifest["trials"] = manifest["trials"][:1]
            manifest["pair_count"] = 1
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "complete case/trial matrix"):
                aggregate(root)

    def test_condition_record_identity_must_match_enclosing_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            treatment = manifest["trials"][0]["conditions"]["with_skill"]
            treatment["case_id"] = "different-case"
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "does not match its enclosing pair"):
                aggregate(root)

    def test_inconsistent_grading_summary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            path = root / "eval-case" / "trial-001" / "with_skill" / "grading.json"
            grading = json.loads(path.read_text(encoding="utf-8"))
            grading["summary"]["passed"] = 0
            _write_json(path, grading)
            manifest = json.loads((root / "run_manifest.json").read_text(encoding="utf-8"))
            record = manifest["trials"][0]["conditions"]["with_skill"]
            record["grading_sha256"] = _sha256(path)
            _write_json(root / "run_manifest.json", manifest)
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                aggregate(root)

    def test_control_exposure_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_run(root, [(False, True)])
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["trials"][0]["conditions"]["without_skill"]["available_skills"] = [
                "candidate"
            ]
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "control"):
                aggregate(root)


class EvaluatorMutationTests(unittest.TestCase):
    def test_sealed_run_accepts_good_and_rejects_corrupt_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_sealed_marker_run(root)
            report = aggregate(root)
            self.assertEqual(report["verdict"], "improved")
            self.assertTrue(report["artifact_valid"])
            self.assertEqual(
                report["task_success"]["pair_outcomes"],
                {
                    "improved": 2,
                    "regressed": 0,
                    "tied_pass": 0,
                    "tied_fail": 0,
                },
            )

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_sealed_marker_run(root)
            response = (
                root
                / "eval-case"
                / "trial-001"
                / "with_skill"
                / "outputs"
                / "response.md"
            )
            response.write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "response_sha256 does not match"):
                aggregate(root)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_sealed_marker_run(root)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["trials"].pop()
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "complete case/trial matrix"):
                aggregate(root)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _make_sealed_marker_run(root)
            grading_path = (
                root
                / "eval-case"
                / "trial-001"
                / "with_skill"
                / "grading.json"
            )
            grading = json.loads(grading_path.read_text(encoding="utf-8"))
            grading["summary"]["passed"] = 0
            _write_json(grading_path, grading)
            manifest_path = root / "run_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["trials"][0]["conditions"]["with_skill"][
                "grading_sha256"
            ] = _sha256(grading_path)
            _write_json(manifest_path, manifest)
            with self.assertRaisesRegex(ValueError, "summary is inconsistent"):
                aggregate(root)

    def test_sealed_marker_grader_rejects_a_wrong_marker(self) -> None:
        graders = [
            {
                "name": "Uses the exact sealed marker value",
                "type": "json_exact",
                "path": ".acme/sealed-marker.json",
                "expected": {
                    "schema": "acme.sealed-marker/v1",
                    "status": "ready",
                    "owner": "skillbench-causal-pilot-integrity-0001",
                },
            }
        ]
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            _write_json(
                workspace / ".acme" / "sealed-marker.json",
                {
                    "schema": "acme.sealed-marker/v1",
                    "status": "ready",
                    "owner": "wrong-owner",
                },
            )
            grading = grade_case(
                workspace=workspace,
                response="sealed marker prepared\n",
                graders=graders,
            )
            self.assertEqual(grading["summary"]["failed"], 1)

    def test_deliberate_response_mutations_fail_deterministic_graders(self) -> None:
        graders = [
            {
                "name": "Preserves required fact",
                "type": "response_contains",
                "value": "threshold=28",
            },
            {
                "name": "Includes acceptance evidence",
                "type": "response_contains",
                "value": "CHECK: PASS",
            },
            {
                "name": "Stays within scope",
                "type": "response_not_contains",
                "value": "edited-unrelated-file",
            },
        ]
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            reference = "threshold=28\nCHECK: PASS\n"
            self.assertEqual(
                grade_case(
                    workspace=workspace,
                    response=reference,
                    graders=graders,
                )["summary"]["failed"],
                0,
            )
            mutations = [
                "threshold=29\nCHECK: PASS\n",
                "threshold=28\n",
                "threshold=28\nCHECK: PASS\nedited-unrelated-file\n",
            ]
            for mutation in mutations:
                with self.subTest(mutation=mutation):
                    self.assertGreater(
                        grade_case(
                            workspace=workspace,
                            response=mutation,
                            graders=graders,
                        )["summary"]["failed"],
                        0,
                    )


class ModelGraderTests(unittest.TestCase):
    def test_json_fence_is_accepted(self) -> None:
        self.assertEqual(
            _parse_grade(
                '```json\n{"passed": true, "reason": "All criteria met."}\n```'
            ),
            {"passed": True, "reason": "All criteria met."},
        )


if __name__ == "__main__":
    unittest.main()
