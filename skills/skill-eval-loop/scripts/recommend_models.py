#!/usr/bin/env python3
"""Discover harness models and recommend a transparent eval configuration."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

from eval_spec import harness_invocation_counts, load_suite
from runtime_adapters import HARNESS_NAMES, resolve_harness


TIER_ORDER = ("budget", "balanced", "quality")
BUDGET_MARKERS = ("luna", "mini", "haiku", "flash", "spark", "small")
QUALITY_MARKERS = ("sol", "opus", "ultra", "max", "pro")


@dataclass(frozen=True)
class ModelOption:
    id: str
    tier: str
    source: str
    description: str = ""


def infer_tier(model_id: str, description: str = "") -> str:
    model_name = model_id.rsplit("/", 1)[-1]
    tokens = set(re.findall(r"[a-z]+", f"{model_name} {description}".lower()))
    if tokens.intersection(BUDGET_MARKERS):
        return "budget"
    if tokens.intersection(QUALITY_MARKERS):
        return "quality"
    return "balanced"


def parse_pi_models(output: str) -> list[ModelOption]:
    models: list[ModelOption] = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[:2] == ["provider", "model"]:
            continue
        provider, model = fields[:2]
        model_id = f"{provider}/{model}"
        models.append(
            ModelOption(model_id, infer_tier(model_id), "pi --list-models")
        )
    return models


def _explicit_models(value: str) -> list[ModelOption]:
    return [
        ModelOption(model_id, infer_tier(model_id), "user-supplied inventory")
        for model_id in (item.strip() for item in value.split(","))
        if model_id
    ]


def _codex_models() -> list[ModelOption]:
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    cache = codex_home / "models_cache.json"
    if not cache.is_file():
        raise FileNotFoundError(
            "Codex has no models cache; open Codex once to refresh its authenticated "
            "model picker, or pass --models with exact comma-separated ids"
        )
    data = json.loads(cache.read_text(encoding="utf-8"))
    return [
        ModelOption(
            id=str(item["slug"]),
            tier=infer_tier(
                str(item["slug"]),
                str(item.get("description", "")),
            ),
            source=f"Codex authenticated cache ({data.get('fetched_at', 'unknown time')})",
            description=str(item.get("description", "")),
        )
        for item in data.get("models", [])
        if isinstance(item, dict)
        and isinstance(item.get("slug"), str)
        and item.get("visibility", "list") == "list"
    ]


def _hermes_models() -> list[ModelOption]:
    hermes_home = Path(
        os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    ).expanduser()
    cache = hermes_home / "provider_models_cache.json"
    if not cache.is_file():
        raise FileNotFoundError(
            "Hermes has no authenticated provider-model cache; run `hermes model` "
            "to configure a provider, or pass --models with exact ids"
        )
    data = json.loads(cache.read_text(encoding="utf-8"))
    models: list[ModelOption] = []
    for provider, record in data.items():
        if not isinstance(record, dict) or not isinstance(record.get("models"), list):
            continue
        for value in record["models"]:
            if not isinstance(value, str) or not value.strip():
                continue
            model_id = value if "/" in value else f"{provider}/{value}"
            models.append(
                ModelOption(
                    model_id,
                    infer_tier(model_id),
                    "Hermes authenticated provider cache",
                )
            )
    return models


def discover_models(
    *,
    harness: str,
    executable: str,
    explicit: str = "",
) -> list[ModelOption]:
    if explicit.strip():
        models = _explicit_models(explicit)
    elif harness == "pi":
        completed = subprocess.run(
            [executable, "--list-models"],
            text=True,
            capture_output=True,
            check=True,
            timeout=30,
        )
        models = parse_pi_models(completed.stdout)
    elif harness == "codex":
        models = _codex_models()
    elif harness == "hermes":
        models = _hermes_models()
    else:
        raise RuntimeError(
            "Claude Code does not expose a stable non-interactive model inventory; "
            "after `claude auth status`, pass --models with the exact ids shown by "
            "its model picker"
        )
    unique = {model.id: model for model in models}
    if not unique:
        raise RuntimeError(
            f"no available {harness} models were discovered; authenticate a provider "
            "or pass --models with exact comma-separated ids"
        )
    return sorted(unique.values(), key=lambda item: (TIER_ORDER.index(item.tier), item.id))


def _pick_option(
    tiered: dict[str, list[ModelOption]],
    preference: tuple[str, ...],
) -> ModelOption:
    for tier in preference:
        if tiered[tier]:
            return tiered[tier][-1]
    raise ValueError("model inventory is empty")


def build_recommendation(
    *,
    harness: str,
    models: list[ModelOption],
    task_profile: str,
    case_count: int,
    model_rubric_count: int,
    counter_reference_count: int = 0,
    trials: int = 1,
    model_rubric_counts: list[int] | None = None,
    counter_reference_declared: list[bool] | None = None,
) -> dict[str, object]:
    if not models:
        raise ValueError("model inventory is empty")
    if task_profile not in {"simple", "standard", "complex", "portability"}:
        raise ValueError("unsupported task profile")
    tiered = {
        tier: sorted(
            (model for model in models if model.tier == tier),
            key=lambda item: item.id,
        )
        for tier in TIER_ORDER
    }
    budget_option = _pick_option(tiered, ("budget", "balanced", "quality"))
    balanced_option = _pick_option(tiered, ("balanced", "quality", "budget"))
    quality_option = _pick_option(tiered, ("quality", "balanced", "budget"))
    budget = budget_option.id
    balanced = balanced_option.id
    quality = quality_option.id
    frontier = [budget, balanced, quality]
    frontier = list(dict.fromkeys(frontier))
    recommended_targets = frontier if task_profile == "portability" else []
    preference = {
        "simple": ("budget", "balanced", "quality"),
        "standard": ("balanced", "quality", "budget"),
        "complex": ("quality", "balanced", "budget"),
        "portability": ("balanced", "quality", "budget"),
    }[task_profile]
    target = (
        None
        if task_profile == "portability"
        else _pick_option(tiered, preference).id
    )
    judge = quality if model_rubric_count else None
    if case_count < 0 or model_rubric_count < 0:
        raise ValueError("case and model-rubric counts must be non-negative")
    if counter_reference_count < 0 or counter_reference_count > case_count:
        raise ValueError("counter_reference_count must be between zero and case_count")
    if (model_rubric_counts is None) != (counter_reference_declared is None):
        raise ValueError(
            "model_rubric_counts and counter_reference_declared must be supplied together"
        )
    if counter_reference_count and model_rubric_counts is None:
        raise ValueError(
            "counter-reference invocation counts require exact per-case vectors"
        )
    # Preserve the original direct-call API. New callers can supply exact
    # per-case data, which is required when any counter-reference is declared.
    if model_rubric_counts is None:
        if case_count == 0 and model_rubric_count:
            raise ValueError("zero cases cannot contain model-rubric graders")
        counts = (
            [model_rubric_count, *([0] * (case_count - 1))]
            if case_count
            else []
        )
    else:
        counts = model_rubric_counts
        if (
            len(counts) != case_count
            or any(type(count) is not int or count < 0 for count in counts)
            or sum(counts) != model_rubric_count
        ):
            raise ValueError("model_rubric_counts must match the supplied totals")
    if counter_reference_declared is None:
        counters = [False] * case_count
    else:
        counters = counter_reference_declared
        if (
            len(counters) != case_count
            or any(type(declared) is not bool for declared in counters)
            or sum(counters) != counter_reference_count
        ):
            raise ValueError("counter_reference_declared must match supplied totals")
    invocation_counts = harness_invocation_counts(
        trials=trials,
        model_rubric_counts=counts,
        counter_reference_declared=counters,
    )
    return {
        "harness": harness,
        "task_profile": task_profile,
        "inventory": [asdict(model) for model in models],
        "frontier": {
            "budget": budget,
            "balanced": balanced,
            "quality": quality,
        },
        "frontier_fallbacks": {
            "budget": budget_option.tier != "budget",
            "balanced": balanced_option.tier != "balanced",
            "quality": quality_option.tier != "quality",
        },
        "recommended_target": target,
        "recommended_targets": recommended_targets,
        "recommended_judge": judge,
        "judge_independence": (
            "not_needed"
            if judge is None
            else "same_model"
            if judge == target
            else "different_model"
        ),
        "pilot_trials": trials,
        "pilot_harness_invocations": invocation_counts["total"],
        "pilot_harness_invocation_counts": invocation_counts,
        "full_run_harness_invocations": None,
        "provider_model_calls": "unknown",
        "cost": "unknown unless the selected harness reports pricing",
        "confirmation_required": True,
        "limits": [
            "Tier labels are transparent name/description heuristics, not measured quality.",
            "Availability does not prove sufficient quota for the planned run.",
            "Use the intended deployment model for release claims.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recommend a no-call model configuration for one skill eval."
    )
    parser.add_argument("--skill-path", required=True, type=Path)
    parser.add_argument("--harness", required=True, choices=HARNESS_NAMES)
    parser.add_argument("--harness-bin")
    parser.add_argument(
        "--task-profile",
        required=True,
        choices=("simple", "standard", "complex", "portability"),
    )
    parser.add_argument(
        "--models",
        default="",
        help="Exact comma-separated model ids when native discovery is unavailable.",
    )
    args = parser.parse_args(argv)
    try:
        executable, harness_version = resolve_harness(args.harness, args.harness_bin)
        suite = load_suite(args.skill_path)
        models = discover_models(
            harness=args.harness,
            executable=executable,
            explicit=args.models,
        )
        model_rubric_count = sum(
            sum(grader["type"] == "model_rubric" for grader in case["graders"])
            for case in suite["evals"]
        )
        report = build_recommendation(
            harness=args.harness,
            models=models,
            task_profile=args.task_profile,
            case_count=len(suite["evals"]),
            model_rubric_count=model_rubric_count,
            counter_reference_count=sum(
                case.get("counter_reference") is not None
                for case in suite["evals"]
            ),
            model_rubric_counts=[
                sum(grader["type"] == "model_rubric" for grader in case["graders"])
                for case in suite["evals"]
            ],
            counter_reference_declared=[
                case.get("counter_reference") is not None
                for case in suite["evals"]
            ],
        )
        report["harness_version"] = harness_version
        report["skill_name"] = suite["skill_name"]
        report["case_count"] = len(suite["evals"])
        report["model_rubric_count"] = model_rubric_count
        print(json.dumps(report, indent=2))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
