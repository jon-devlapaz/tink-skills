#!/usr/bin/env python3
"""Opt-in engram council for seed-me: build the lens prompt, then apply the settle-or-surface rule.

Read-only, standard library only. Lenses are simulations and advise only: a settled decision carries the
human's standing delegation as its authority, never the lenses'. See references/engram-council.md.
"""
import argparse
import json
from pathlib import Path
import re
import sys

LINE = re.compile(r"^(D\w+)\s*\|\s*(.+?)\s*\|\s*CHANGES-MEANING:\s*(yes|no)\s*\|\s*(.*)$", re.I)
MISSING = re.compile(r"^MISSING:\s*(.*)$", re.I)
UNDO = ("cheap", "moderate", "hard")


def fail(message):
    print(f"engram_council: {message}", file=sys.stderr)
    raise SystemExit(2)


def load_decisions(path):
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        fail(f"cannot read decisions file: {error}")
    if not isinstance(data, list) or not data:
        fail("decisions file must be a non-empty JSON list")
    seen = set()
    for d in data:
        ok = (isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"].strip() and isinstance(d.get("title"), str)
              and isinstance(d.get("options"), list) and len(d["options"]) >= 2 and all(isinstance(o, str) and o.strip() for o in d["options"])
              and d.get("undo") in UNDO and isinstance(d.get("grounded"), bool))
        if not ok or d["id"] in seen:
            fail("each decision needs a unique id, a title, two or more options, undo (cheap|moderate|hard) and grounded (true|false)")
        seen.add(d["id"])
    return data


def ask(decisions, idea):
    lines = [f"# The hunch\n{idea}\n", "# Candidate decisions (answer ALL, in order)"]
    for d in decisions:
        lines.append(f"{d['id']} {d['title']}: " + " / ".join(d["options"]) + ".")
    lines += ["", "# Answer format (strict, one line per decision, no prose outside it)",
              "Dn | your choice | CHANGES-MEANING: yes or no | reason in at most 20 words",
              "CHANGES-MEANING means: would the other choice change what the hunch actually IS (the problem solved, who it is for, "
              "where its boundary sits, or what done means), as opposed to merely how it is built.",
              "After the lines, add one line: MISSING: any decision that changes the meaning of the hunch that the list leaves out, or \"none\"."]
    return "\n".join(lines) + "\n"


def parse_lens(text, decisions):
    by_id = {d["id"]: d for d in decisions}
    answers, missing = {}, []
    for raw in text.splitlines():
        raw = raw.strip()
        m = LINE.match(raw)
        if m and m.group(1) in by_id:
            choice = next((o for o in by_id[m.group(1)]["options"] if o.lower() == m.group(2).strip().lower()), None)
            if choice is not None and m.group(1) not in answers:
                answers[m.group(1)] = (choice, m.group(3).lower() == "yes", m.group(4).strip())
            continue
        m = MISSING.match(raw)
        if m and m.group(1).strip().lower() not in ("", "none", "none."):
            missing.append(m.group(1).strip())
    return answers, missing


def decide(decisions, lenses):
    parsed = {name: parse_lens(Path(path).read_text(), decisions) for name, path in lenses.items()}
    report = {"lenses": {}, "missing": [], "decisions": []}
    for name, (answers, missing) in parsed.items():
        report["lenses"][name] = {"valid": len(answers), "abstained": [d["id"] for d in decisions if d["id"] not in answers]}
        report["missing"] += [{"lens": name, "text": t} for t in missing]
    for d in decisions:
        out = {"id": d["id"], "title": d["title"]}
        votes = {name: a[d["id"]] for name, (a, _) in parsed.items() if d["id"] in a}
        out["choices"] = {name: v[0] for name, v in votes.items()}
        out["flags"] = sorted(name for name, v in votes.items() if v[1])
        if d["undo"] == "hard":
            out.update(action="surface", reason="hard to undo: the human's instinct comes first")
        elif not d["grounded"]:
            out.update(action="surface", reason="ungrounded: cannot settle by delegation")
        elif len(votes) < 2:
            out.update(action="surface", reason="fewer than two valid lens answers")
        else:
            tally = {}
            for name, v in votes.items():
                tally.setdefault(v[0], []).append(name)
            ranked = sorted(tally.items(), key=lambda kv: -len(kv[1]))
            diverge = len(tally) > 1
            if diverge and out["flags"]:
                out.update(action="surface", reason="lenses diverge and at least one flags a change of meaning")
            elif diverge and len(ranked[0][1]) == len(ranked[1][1]):
                out.update(action="surface", reason="no strict plurality among the lenses")
            else:
                choice, winners = ranked[0]
                out.update(action="settle", choice=choice, authority="delegated", boundary=bool(out["flags"]),
                           dissent=sorted(n for n in votes if n not in winners),
                           evidence=[f"engram:{n} (simulation, not the person) chose '{votes[n][0]}': {votes[n][2] or 'no reason given'}"
                                     for n in sorted(votes)],
                           authority_source="standing delegation (human opt-in); engram lenses: " + ", ".join(sorted(votes)))
        report["decisions"].append(out)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    a = commands.add_parser("ask")
    a.add_argument("decisions")
    a.add_argument("--idea", required=True)
    d = commands.add_parser("decide")
    d.add_argument("decisions")
    d.add_argument("--lens", action="append", required=True, metavar="NAME=FILE")
    args = parser.parse_args()
    decisions = load_decisions(args.decisions)
    if args.command == "ask":
        sys.stdout.write(ask(decisions, args.idea))
        return
    lenses = {}
    for item in args.lens:
        name, _, path = item.partition("=")
        if not name or not path:
            fail("--lens needs NAME=FILE")
        lenses[name] = path
    print(json.dumps(decide(decisions, lenses), indent=1))


if __name__ == "__main__":
    main()
