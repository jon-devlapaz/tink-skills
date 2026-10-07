"""Shared fixture: the saved seed a session needs before `end --status completed`."""
from pathlib import Path


def save_seed(session, directory, status_line=None):
    """Write `<session>/seed-contract.md` with the line 1 a completed session needs (confirmed, or simulated for a simulated session).

    Tests that are about ledger behavior, not about confirmation, use this instead of running `seed confirm`.
    """
    directory = Path(directory)
    if status_line is None:
        operator = session.load(directory).get("operator", "human")
        status_line = session.STATUS_SIMULATED if operator == "simulated" else session.STATUS_CONFIRMED
    (directory / session.SEED_FILE).write_text(status_line + "\n# Seed contract: fixture\nrevision: r1        date: 2026-10-06\n\n## You are confirming\n- Goal: fixture\n", encoding="utf-8")
