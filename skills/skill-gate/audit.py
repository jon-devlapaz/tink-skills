"""Composition of feature, risk, and compatibility analysis."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from _common import SCHEMA_VERSION
from compat import CompatibilityReport, evaluate_compatibility
from features import SkillFeatures, extract_features
from risk import RiskReport, profile_risk

# ============================================================================
# E2E Skill Audit Analysis
# ============================================================================

@dataclass
class SkillAuditReport:
    schema_version: str
    skill_name: str
    skill_dir: str
    features: SkillFeatures
    risk: RiskReport
    compatibility: CompatibilityReport

    @property
    def vector_hash(self) -> str:
        return self.features.vector_hash

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "skill_name": self.skill_name,
            "skill_dir": self.skill_dir,
            "vector_hash": self.features.vector_hash,
            "features": {
                "file_count": self.features.file_count,
                "total_bytes": self.features.total_bytes,
                "tools": self.features.tools,
                "vector": self.features.vector,
                "python_files_count": self.features.python_files_count,
                "shell_files_count": self.features.shell_files_count,
                "warnings": self.features.warnings,
            },
            "risk": {
                "verdict": self.risk.verdict,
                "overall_score": self.risk.overall_score,
                "redlines_triggered": self.risk.redlines_triggered,
                "factors": {
                    k: {
                        "name": v.name,
                        "weight": v.weight,
                        "score": v.score,
                        "findings": v.findings,
                    }
                    for k, v in self.risk.factors.items()
                },
            },
            "compatibility": {
                "target_harness": self.compatibility.target_harness,
                "status": self.compatibility.status,
                "missing_tools": self.compatibility.missing_tools,
                "declared_tools": self.compatibility.declared_tools,
            },
        }


def analyze_skill(skill_dir: str, target_harness: str = "pi") -> SkillAuditReport:
    """Full skill audit: feature extraction, risk profiling, and compatibility check."""
    features = extract_features(skill_dir)
    risk = profile_risk(features)
    compat = evaluate_compatibility(features, target_harness=target_harness)
    return SkillAuditReport(
        schema_version=SCHEMA_VERSION,
        skill_name=features.skill_name,
        skill_dir=str(Path(skill_dir).resolve()),
        features=features,
        risk=risk,
        compatibility=compat,
    )
