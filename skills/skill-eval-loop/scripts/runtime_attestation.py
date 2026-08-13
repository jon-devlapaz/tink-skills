#!/usr/bin/env python3
"""Target-runtime attestation policy for paired skill evaluation.

``trace_metadata`` parses harness traces. This module owns what must be true
for a *target* condition. Aggregate re-parses and applies the same policy as
reason codes without trusting manifest booleans. Write-time callers raise via
``require_target_runtime_attestation``, a thin adapter over evaluate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from runtime_adapters import model_matches


def evaluate_target_trace_attestation(
    metadata: Mapping[str, Any],
    *,
    harness: str,
    requested_model: str,
    recorded_actual_model: object | None = None,
    condition: str | None = None,
    activation_mode: str | None = None,
) -> list[str]:
    """Return machine reason codes for target-trace attestation.

    Empty list means the policy passed. Soft-fail callers (aggregate) extend
    their ``invalid`` list with these codes. Write-time callers use
    ``require_target_runtime_attestation``.

    Forced-skill access is checked only when ``condition`` and
    ``activation_mode`` identify a Codex forced treatment (write-time).
    """
    reasons = evaluate_model_trace_attestation(
        metadata,
        harness=harness,
        requested_model=requested_model,
        recorded_actual_model=recorded_actual_model,
    )
    if (
        harness == "codex"
        and condition == "with_skill"
        and activation_mode == "forced"
        and metadata.get("skill_explicitly_accessed") is not True
    ):
        reasons.append("forced_skill_not_accessed")
    return reasons


def evaluate_model_trace_attestation(
    metadata: Mapping[str, Any],
    *,
    harness: str,
    requested_model: str,
    recorded_actual_model: object | None = None,
) -> list[str]:
    """Return shared model-identity reason codes for targets and judges."""
    reasons: list[str] = []
    if harness == "codex" and not metadata.get("attestation_trace_path"):
        reasons.append("attestation_trace_missing")
    if metadata.get("model_attested") is not True:
        reasons.append("model_not_attested")
    attested_model = metadata.get("actual_model")
    if not model_matches(requested_model, attested_model):
        reasons.append("model_mismatch")
    if recorded_actual_model is not None and not model_matches(
        str(recorded_actual_model or ""),
        attested_model,
    ):
        reasons.append("manifest_model_mismatch")
    return reasons


def require_target_runtime_attestation(
    metadata: Mapping[str, Any],
    *,
    harness: str,
    requested_model: str,
    condition: str,
    activation_mode: str,
    skill_name: str,
    trace_path: Path,
) -> None:
    """Raise for the first write-time target failure in evaluation order.

    Forced-skill access is write-time only. Aggregate callers must omit
    ``condition`` and ``activation_mode`` when re-evaluating retained traces.
    """
    reasons = evaluate_target_trace_attestation(
        metadata,
        harness=harness,
        requested_model=requested_model,
        condition=condition,
        activation_mode=activation_mode,
    )
    if not reasons:
        return
    raise RuntimeError(
        _write_time_message(
            reasons[0],
            requested_model=requested_model,
            actual_model=metadata.get("actual_model"),
            skill_name=skill_name,
            trace_path=trace_path,
        )
    )


def require_judge_runtime_attestation(
    metadata: Mapping[str, Any],
    *,
    harness: str,
    requested_model: str,
    trace_path: Path,
) -> None:
    """Raise for the first write-time judge failure in evaluation order."""
    reasons = evaluate_model_trace_attestation(
        metadata,
        harness=harness,
        requested_model=requested_model,
    )
    if not reasons:
        return
    reason = reasons[0]
    actual_model = metadata.get("actual_model")
    if reason == "attestation_trace_missing":
        message = (
            f"judge model {requested_model} was not attested; persisted Codex "
            f"rollout is missing; see {trace_path}"
        )
    elif reason == "model_not_attested":
        message = f"judge model {requested_model} was not attested; see {trace_path}"
    elif reason == "model_mismatch":
        message = (
            f"requested judge model {requested_model} but attested {actual_model}; "
            f"see {trace_path}"
        )
    else:
        raise ValueError(f"unhandled judge attestation reason: {reason}")
    raise RuntimeError(message)


def _write_time_message(
    reason: str,
    *,
    requested_model: str,
    actual_model: object,
    skill_name: str,
    trace_path: Path,
) -> str:
    if reason == "attestation_trace_missing":
        return (
            f"target model {requested_model} was not attested; persisted Codex "
            f"rollout is missing; see {trace_path}"
        )
    if reason == "model_not_attested":
        return (
            f"target model {requested_model} was not attested; see {trace_path}"
        )
    if reason == "model_mismatch":
        return (
            f"requested target model {requested_model} but attested "
            f"{actual_model}; see {trace_path}"
        )
    if reason == "forced_skill_not_accessed":
        return (
            f"forced target skill {skill_name} was not explicitly accessed; "
            f"see {trace_path}"
        )
    raise ValueError(f"unhandled target attestation reason: {reason}")
