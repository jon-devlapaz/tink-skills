#!/usr/bin/env python3
"""Validate and grade local skill-evaluation suites."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


GRADER_TYPES = {
    "response_contains",
    "response_not_contains",
    "response_regex",
    "markdown_table_column_regex",
    "file_exists",
    "json_exact",
    "model_rubric",
}
# Counter-reference grades a wrong *response* on the gold reference workspace.
# Workspace-only graders (file_exists / json_exact) cannot discriminate and must
# not be paired with counter_reference without a response-sensitive grader.
RESPONSE_SENSITIVE_GRADER_TYPES = frozenset(
    {
        "response_contains",
        "response_not_contains",
        "response_regex",
        "markdown_table_column_regex",
        "model_rubric",
    }
)
SKILL_LOADING_POLICIES = {"required", "optional", "forbidden"}
SUITE_TYPES = {"capability", "regression"}
DATASET_ORIGINS = {"author_derived", "held_out", "production_regression"}
PROVENANCE_SOURCE_TYPES = {
    "author_scenario",
    "independent_task",
    "production_trace",
    "user_correction",
    "incident",
}
BEHAVIOR_CLASSES = {"positive", "edge", "negative"}
ROUTING_CLASSES = {"should_trigger", "should_not_trigger", "ambiguous"}
TOOL_PROFILES = {"no_tools", "read_only", "read_write", "coding"}
ACTIVATION_MODES = {"forced", "autonomous"}


def canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def safe_relative_path(root: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty relative path")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} must stay below {root}")
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"{label} escapes {root}") from exc
    return resolved


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_distribution_policy(
    value: object,
    source: Path,
) -> dict[str, float | int]:
    label = f"{source}.distribution_policy"
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    minimum_pairs = value.get("minimum_pairs")
    minimum_effect_size = value.get("minimum_effect_size")
    confidence_level = value.get("confidence_level")
    if type(minimum_pairs) is not int or minimum_pairs < 3:
        raise ValueError(f"{label}.minimum_pairs must be an integer >= 3")
    if not isinstance(minimum_effect_size, (int, float)) or not (
        0 < float(minimum_effect_size) <= 1
    ):
        raise ValueError(
            f"{label}.minimum_effect_size must be greater than 0 and at most 1"
        )
    if not isinstance(confidence_level, (int, float)) or not (
        0.8 <= float(confidence_level) < 1
    ):
        raise ValueError(
            f"{label}.confidence_level must be at least 0.8 and below 1"
        )
    return {
        "minimum_pairs": minimum_pairs,
        "minimum_effect_size": float(minimum_effect_size),
        "confidence_level": float(confidence_level),
    }


def _load_provenance(
    *,
    suite_root: Path,
    value: object,
    source: Path,
    case_ids: set[str],
    case_hashes: dict[str, str],
    suite_hash: str,
    dataset_origin: str,
) -> tuple[dict[str, Any], str]:
    provenance_path = safe_relative_path(
        suite_root,
        value,
        f"{source}.provenance_manifest",
    )
    data = json.loads(provenance_path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError(f"{provenance_path} must use schema_version 1")
    records = data.get("cases")
    if not isinstance(records, list):
        raise ValueError(f"{provenance_path}.cases must be a list")
    by_case: dict[str, Any] = {}
    seen_source_ids: set[str] = set()
    for index, record in enumerate(records, start=1):
        label = f"{provenance_path}.cases[{index}]"
        if not isinstance(record, dict):
            raise ValueError(f"{label} must be an object")
        case_id = record.get("case_id")
        if case_id not in case_ids or case_id in by_case:
            raise ValueError(f"{label}.case_id is unknown or duplicate")
        origin = record.get("origin")
        if origin != dataset_origin:
            raise ValueError(
                f"{label}.origin must match suite dataset_origin {dataset_origin!r}"
            )
        source_id = record.get("source_id")
        if not isinstance(source_id, str) or not source_id.strip():
            raise ValueError(f"{label}.source_id must be non-empty")
        if source_id in seen_source_ids:
            raise ValueError(f"{label}.source_id must be unique")
        seen_source_ids.add(source_id)
        source_type = record.get("source_type")
        if source_type not in PROVENANCE_SOURCE_TYPES:
            raise ValueError(
                f"{label}.source_type must be one of "
                f"{sorted(PROVENANCE_SOURCE_TYPES)}"
            )
        allowed_by_origin = {
            "author_derived": {"author_scenario"},
            "held_out": {"independent_task"},
            "production_regression": {
                "production_trace",
                "user_correction",
                "incident",
            },
        }
        if source_type not in allowed_by_origin[str(origin)]:
            raise ValueError(
                f"{label}.source_type is inconsistent with origin {origin!r}"
            )
        if not isinstance(record.get("observed_at"), str) or not record[
            "observed_at"
        ].strip():
            raise ValueError(f"{label}.observed_at must be non-empty")
        if not isinstance(record.get("task_author"), str) or not record[
            "task_author"
        ].strip():
            raise ValueError(f"{label}.task_author must be non-empty")
        artifact = safe_relative_path(
            suite_root,
            record.get("artifact"),
            f"{label}.artifact",
        )
        expected_hash = record.get("artifact_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected_hash or "")):
            raise ValueError(f"{label}.artifact_sha256 must be a sha256")
        if not artifact.is_file():
            raise ValueError(f"{label}.artifact does not exist")
        if _sha256_file(artifact) != expected_hash:
            raise ValueError(f"{label}.artifact_sha256 does not match artifact")
        expected_case_hash = record.get("case_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", str(expected_case_hash or "")):
            raise ValueError(f"{label}.case_sha256 must be a sha256")
        if expected_case_hash != case_hashes[str(case_id)]:
            raise ValueError(
                f"{label}.case_sha256 does not match eval case"
            )
        by_case[str(case_id)] = {
            **record,
            "artifact": str(artifact.relative_to(suite_root)),
        }
    if set(by_case) != case_ids:
        missing = sorted(case_ids - set(by_case))
        raise ValueError(
            f"{provenance_path} does not cover every eval case: missing {missing}"
        )
    expected_suite_hash = data.get("suite_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected_suite_hash or "")):
        raise ValueError(f"{provenance_path}.suite_sha256 must be a sha256")
    if expected_suite_hash != suite_hash:
        raise ValueError(
            f"{provenance_path}.suite_sha256 does not match eval suite"
        )
    return by_case, _sha256_file(provenance_path)


def _validate_grader(grader: object, case_label: str, index: int) -> dict[str, Any]:
    label = f"{case_label}.graders[{index}]"
    if not isinstance(grader, dict):
        raise ValueError(f"{label} must be an object")
    grader_type = grader.get("type")
    if grader_type not in GRADER_TYPES:
        raise ValueError(
            f"{label}.type must be one of {sorted(GRADER_TYPES)}"
        )
    name = grader.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{label}.name must be non-empty")
    normalized = dict(grader)
    normalized["name"] = name.strip()
    if grader_type in {
        "response_contains",
        "response_not_contains",
        "response_regex",
        "markdown_table_column_regex",
    }:
        value_key = (
            "pattern"
            if grader_type in {"response_regex", "markdown_table_column_regex"}
            else "value"
        )
        if not isinstance(grader.get(value_key), str) or not grader[value_key]:
            raise ValueError(f"{label}.{value_key} must be non-empty")
        if grader_type in {"response_regex", "markdown_table_column_regex"}:
            try:
                re.compile(grader["pattern"])
            except re.error as exc:
                raise ValueError(f"{label}.pattern is invalid: {exc}") from exc
        if grader_type == "markdown_table_column_regex":
            if not isinstance(grader.get("column"), str) or not grader["column"]:
                raise ValueError(f"{label}.column must be non-empty")
    elif grader_type == "model_rubric":
        has_rubric = (
            isinstance(grader.get("rubric"), str)
            and bool(grader["rubric"].strip())
        )
        has_criteria = (
            isinstance(grader.get("criteria"), list)
            and bool(grader["criteria"])
        )
        if not has_rubric and not has_criteria:
            raise ValueError(f"{label} needs a rubric or criteria")
    elif grader_type == "file_exists":
        if not isinstance(grader.get("path"), str):
            raise ValueError(f"{label}.path must be a string")
    elif grader_type == "json_exact":
        if not isinstance(grader.get("path"), str):
            raise ValueError(f"{label}.path must be a string")
        if "expected" not in grader:
            raise ValueError(f"{label}.expected is required")
    return normalized


def load_suite(skill_path: Path, evals_path: Path | None = None) -> dict[str, Any]:
    skill_path = skill_path.resolve()
    source = (evals_path or skill_path / "evals" / "evals.json").resolve()
    data = json.loads(source.read_text(encoding="utf-8"))
    schema_version = data.get("schema_version")
    if schema_version not in {2, 3}:
        raise ValueError(f"{source} must use schema_version 2 or 3")
    if data.get("suite_type") not in SUITE_TYPES:
        raise ValueError(
            f"{source}.suite_type must be one of {sorted(SUITE_TYPES)}"
        )
    if data.get("dataset_origin") not in DATASET_ORIGINS:
        raise ValueError(
            f"{source}.dataset_origin must be one of {sorted(DATASET_ORIGINS)}"
        )
    if data.get("tool_profile") not in TOOL_PROFILES:
        raise ValueError(
            f"{source}.tool_profile must be one of {sorted(TOOL_PROFILES)}"
        )
    activation_mode = data.get("activation_mode", "forced")
    if activation_mode not in ACTIVATION_MODES:
        raise ValueError(
            f"{source}.activation_mode must be one of "
            f"{sorted(ACTIVATION_MODES)}"
        )
    if activation_mode == "autonomous" and schema_version != 3:
        raise ValueError(
            f"{source}.activation_mode=autonomous requires schema_version 3"
        )
    if data.get("skill_name") != skill_path.name:
        raise ValueError(
            f"{source}.skill_name must match directory {skill_path.name!r}"
        )
    cases = data.get("evals")
    if not isinstance(cases, list) or not cases:
        raise ValueError(f"{source}.evals must be a non-empty list")
    seen_ids: set[str] = set()
    normalized_cases: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        label = f"evals[{index}]"
        if not isinstance(case, dict):
            raise ValueError(f"{label} must be an object")
        case_id = str(case.get("id", "")).strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", case_id):
            raise ValueError(f"{label}.id must be lowercase kebab-case")
        if case_id in seen_ids:
            raise ValueError(f"duplicate eval id: {case_id}")
        seen_ids.add(case_id)
        prompt = case.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{label}.prompt must be non-empty")
        loading = case.get("expected_skill_loading", "required")
        if loading not in SKILL_LOADING_POLICIES:
            raise ValueError(
                f"{label}.expected_skill_loading must be one of "
                f"{sorted(SKILL_LOADING_POLICIES)}"
            )
        behavior_class = case.get("behavior_class")
        if behavior_class not in BEHAVIOR_CLASSES:
            raise ValueError(
                f"{label}.behavior_class must be one of "
                f"{sorted(BEHAVIOR_CLASSES)}"
            )
        routing_class = case.get("routing_class")
        if schema_version == 3 and routing_class not in ROUTING_CLASSES:
            raise ValueError(
                f"{label}.routing_class must be one of "
                f"{sorted(ROUTING_CLASSES)}"
            )
        if schema_version == 3:
            if routing_class == "should_trigger" and loading != "required":
                raise ValueError(
                    f"{label}.should_trigger requires expected_skill_loading=required"
                )
            if routing_class == "should_not_trigger" and loading != "forbidden":
                raise ValueError(
                    f"{label}.should_not_trigger requires "
                    "expected_skill_loading=forbidden"
                )
            if routing_class == "ambiguous" and loading == "optional":
                raise ValueError(
                    f"{label}.ambiguous routing must declare required or forbidden"
                )
        graders = case.get("graders")
        if not isinstance(graders, list) or not graders:
            raise ValueError(f"{label}.graders must be a non-empty list")
        reference = case.get("reference")
        if not isinstance(reference, dict):
            raise ValueError(f"{label}.reference must be an object")
        if not isinstance(reference.get("response", ""), str):
            raise ValueError(f"{label}.reference.response must be a string")
        counter_reference = case.get("counter_reference")
        if counter_reference is not None:
            if not isinstance(counter_reference, dict):
                raise ValueError(f"{label}.counter_reference must be an object")
            if "response" not in counter_reference:
                raise ValueError(
                    f"{label}.counter_reference.response is required "
                    "(empty objects are not allowed)"
                )
            if not isinstance(counter_reference["response"], str):
                raise ValueError(f"{label}.counter_reference.response must be a string")
        normalized = dict(case)
        normalized["id"] = case_id
        normalized["prompt"] = prompt.strip()
        normalized["expected_skill_loading"] = loading
        normalized["routing_class"] = routing_class
        normalized["graders"] = [
            _validate_grader(grader, label, grader_index)
            for grader_index, grader in enumerate(graders, start=1)
        ]
        grader_names = [grader["name"] for grader in normalized["graders"]]
        if len(grader_names) != len(set(grader_names)):
            raise ValueError(f"{label} has a duplicate grader name")
        if counter_reference is not None and not any(
            grader["type"] in RESPONSE_SENSITIVE_GRADER_TYPES
            for grader in normalized["graders"]
        ):
            raise ValueError(
                f"{label}.counter_reference requires at least one "
                "response-sensitive grader "
                f"({', '.join(sorted(RESPONSE_SENSITIVE_GRADER_TYPES))}); "
                "file_exists/json_exact alone cannot discriminate a wrong "
                "response on the gold reference workspace"
            )
        if schema_version == 2:
            for grader_index, grader in enumerate(
                normalized["graders"],
                start=1,
            ):
                if grader["type"] == "model_rubric" and not (
                    isinstance(grader.get("rubric"), str)
                    and grader["rubric"].strip()
                ):
                    raise ValueError(
                        f"{label}.graders[{grader_index}].rubric must be non-empty"
                    )
        if schema_version == 3:
            for grader_index, grader in enumerate(
                normalized["graders"],
                start=1,
            ):
                if grader["type"] != "model_rubric":
                    continue
                grader_label = f"{label}.graders[{grader_index}]"
                criteria = grader.get("criteria")
                if not isinstance(criteria, list) or not criteria:
                    raise ValueError(
                        f"{grader_label}.criteria must be a non-empty list"
                    )
                requirements: list[str] = []
                for criterion_index, criterion in enumerate(criteria, start=1):
                    criterion_label = (
                        f"{grader_label}.criteria[{criterion_index}]"
                    )
                    if not isinstance(criterion, dict):
                        raise ValueError(f"{criterion_label} must be an object")
                    requirement = criterion.get("requirement")
                    prompt_quote = criterion.get("prompt_quote")
                    if (
                        not isinstance(requirement, str)
                        or not requirement.strip()
                    ):
                        raise ValueError(
                            f"{criterion_label}.requirement must be non-empty"
                        )
                    if (
                        not isinstance(prompt_quote, str)
                        or not prompt_quote.strip()
                    ):
                        raise ValueError(
                            f"{criterion_label}.prompt_quote must be non-empty"
                        )
                    if prompt_quote.strip().casefold() not in prompt.casefold():
                        raise ValueError(
                            f"{criterion_label}.prompt_quote must appear in "
                            "the prompt"
                        )
                    requirements.append(requirement.strip())
                grader["rubric"] = (
                    "Pass only if every requirement is met:\n- "
                    + "\n- ".join(requirements)
                )
        normalized_cases.append(normalized)
    suite_root = source.parent if schema_version == 3 else skill_path
    distribution_policy = None
    provenance_records: dict[str, Any] = {}
    provenance_sha256 = None
    if schema_version == 3:
        case_hashes = {
            str(case["id"]): canonical_sha256(case)
            for case in cases
        }
        distribution_policy = _validate_distribution_policy(
            data.get("distribution_policy"),
            source,
        )
        provenance_records, provenance_sha256 = _load_provenance(
            suite_root=suite_root,
            value=data.get("provenance_manifest"),
            source=source,
            case_ids=seen_ids,
            case_hashes=case_hashes,
            suite_hash=canonical_sha256(data),
            dataset_origin=data["dataset_origin"],
        )
    return {
        **data,
        "activation_mode": activation_mode,
        "source_path": str(source),
        "suite_root": str(suite_root),
        "distribution_policy": distribution_policy,
        "provenance_records": provenance_records,
        "provenance_sha256": provenance_sha256,
        "evals": normalized_cases,
    }


def grade_case(
    *,
    workspace: Path,
    response: str,
    graders: list[dict[str, Any]],
    external_grades: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for grader in graders:
        grader_type = grader["type"]
        passed = False
        evidence = ""
        if grader_type == "response_contains":
            needle = grader["value"]
            passed = needle in response
            evidence = f"{needle!r} {'found' if passed else 'not found'} in response"
        elif grader_type == "response_not_contains":
            needle = grader["value"]
            passed = needle not in response
            evidence = f"{needle!r} {'absent' if passed else 'present'} in response"
        elif grader_type == "response_regex":
            match = re.search(grader["pattern"], response)
            passed = match is not None
            evidence = (
                f"matched {match.group(0)!r}"
                if match
                else f"pattern {grader['pattern']!r} did not match"
            )
        elif grader_type == "markdown_table_column_regex":
            column_text = _markdown_column(response, grader["column"])
            match = re.search(grader["pattern"], column_text)
            passed = match is not None
            evidence = (
                f"column {grader['column']!r} matched {match.group(0)!r}"
                if match
                else (
                    f"pattern {grader['pattern']!r} did not match column "
                    f"{grader['column']!r}; observed={column_text!r}"
                )
            )
        elif grader_type == "model_rubric":
            external = (external_grades or {}).get(grader["name"])
            if not isinstance(external, dict):
                raise ValueError(
                    f"missing external model grade for {grader['name']!r}"
                )
            if type(external.get("passed")) is not bool:
                raise ValueError(
                    f"external model grade {grader['name']!r} needs boolean passed"
                )
            passed = external["passed"]
            evidence = str(external.get("evidence", "")).strip()
            if not evidence:
                raise ValueError(
                    f"external model grade {grader['name']!r} needs evidence"
                )
        elif grader_type == "file_exists":
            target = safe_relative_path(workspace, grader["path"], grader["name"])
            passed = target.is_file()
            evidence = f"{grader['path']} {'exists' if passed else 'is absent'}"
        elif grader_type == "json_exact":
            target = safe_relative_path(workspace, grader["path"], grader["name"])
            observed: object = None
            error = ""
            try:
                observed = json.loads(target.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                error = str(exc)
            passed = observed == grader["expected"]
            evidence = (
                f"{grader['path']} exactly matches expected JSON"
                if passed
                else f"observed={observed!r}; error={error or 'none'}"
            )
        results.append(
            {
                "text": grader["name"],
                "passed": passed,
                "evidence": evidence,
                "grader": grader_type,
            }
        )
    passed_count = sum(1 for item in results if item["passed"])
    total = len(results)
    return {
        "grader": {"kind": "deterministic_mixed", "schema_version": 2},
        "expectations": results,
        "summary": {
            "passed": passed_count,
            "failed": total - passed_count,
            "total": total,
            "pass_rate": passed_count / total,
        },
    }


def _markdown_column(markdown: str, column: str) -> str:
    lines = [line.strip() for line in markdown.splitlines() if "|" in line]
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if column not in cells:
            continue
        column_index = cells.index(column)
        values: list[str] = []
        for row in lines[index + 2 :]:
            row_cells = [cell.strip() for cell in row.strip("|").split("|")]
            if len(row_cells) <= column_index:
                break
            values.append(row_cells[column_index].strip('"“”'))
        return "\n".join(values)
    return ""
