"""Eval-contract checker salvaged from agentic-se-skills.

Eval files live in <skill>/evals/*.md. Each must carry the REQUIRED_FIELDS
sections, and name exactly one skill under test from KNOWN_SKILLS.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


KNOWN_SKILLS = {
    "seed-me",
}

REQUIRED_FIELDS = [
    "Scenario",
    "Skill under test",
    "Input prompt",
    "Expected artifacts",
    "Pass criteria",
    "Failure signals",
    "Scoring rubric",
]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _section_body(text: str, field: str) -> str:
    pattern = re.compile(rf"^## {re.escape(field)}\s*$([\s\S]*?)(?=^## |\Z)", re.MULTILINE)
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def check_eval_contracts(root: Path, known_skills: set[str] = KNOWN_SKILLS) -> list[str]:
    errors: list[str] = []
    eval_files = sorted((root / "evals").glob("*.md"))
    if not eval_files:
        return ["no eval markdown files found"]

    for eval_file in eval_files:
        text = eval_file.read_text(encoding="utf-8")
        label = eval_file.relative_to(root)
        for field in REQUIRED_FIELDS:
            body = _section_body(text, field)
            if not body:
                errors.append(f"{label}: missing or empty section '## {field}'")

        skill_body = _section_body(text, "Skill under test")
        named_skills = {skill for skill in known_skills if skill in skill_body}
        if len(named_skills) != 1:
            errors.append(f"{label}: expected exactly one known skill under test, found {sorted(named_skills)}")

    return errors


def main() -> int:
    errors = check_eval_contracts(repo_root())
    if errors:
        print("Eval contract check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Eval contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
