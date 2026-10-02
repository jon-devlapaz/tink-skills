#!/usr/bin/env python3
"""Deterministic conduct checks for seed-me. Read-only, standard library only, no network.

Three groups:
  turns      interviewer turns pulled from a Claude Code transcript (.jsonl)
  ledgers    saved seed-me sessions (ledger.json)
  contracts  seed contract markdown files

Every check is code: regex, counting, or the session validator. Fuzzy judgments belong to a later layer.
"""
import argparse
import json
from pathlib import Path
import re
import sys

SKILL_SCRIPTS = Path(__file__).resolve().parents[1] / "skills/seed-me/scripts"
FORBIDDEN_FOR_OPERATOR = ("ledger", "session.py", "authority", "seed-contract", "SKILL.md", "simulated", "operator agent")
CONFIDENCE = re.compile(r"Confidence:\s*\**\s*([a-z-]+)", re.I)
UNDO = re.compile(r"Undo cost:\s*\**\s*(cheap|moderate|hard)\b", re.I)


# ---------- turns ----------
HEADER = re.compile(r"Question \d+( of \d+)?( ready)?\s*\(")
INSTINCT_LINE = re.compile(r"(?m)^\W*What's your instinct\?")
OPTION_A = re.compile(r"(?m)^\W*Option A\b")
OPTION_B = re.compile(r"(?m)^\W*Option B\b")
SUGGESTION_LINE = re.compile(r"(?m)^\W*My suggestion\b")


def is_instinct_turn(text):
    """The instinct-first form: a line that starts with the question, plus a 'what I found' section."""
    return bool(INSTINCT_LINE.search(text)) and bool(re.search(r"(?i)what i found", text))


def is_option_turn(text):
    """The template's own lines, anchored at line starts. Prose that merely discusses options does not count."""
    both = bool(OPTION_A.search(text) and OPTION_B.search(text))
    partial = bool(SUGGESTION_LINE.search(text) and (OPTION_A.search(text) or OPTION_B.search(text)))
    return both or partial  # a half-formed template turn is still a question turn, so its missing parts get flagged


def is_question_turn(text):
    return is_instinct_turn(text) or is_option_turn(text)


def turn_findings(text, operator_facing=False):
    """Return {rule: (status, detail)} with status pass | fail | na."""
    out = {}
    instinct = is_instinct_turn(text)
    if operator_facing:
        leaked = [w for w in FORBIDDEN_FOR_OPERATOR if w.lower() in text.lower()]
        out["operator-no-leak"] = ("fail", "leaks: " + ", ".join(leaked)) if leaked else ("pass", "")
    elif is_question_turn(text) and HEADER.search(text):
        out["ledger-footer"] = ("pass", "") if re.search(r"(?m)^Ledger:\s*\S", text) else ("fail", "no 'Ledger:' line")
    if not is_question_turn(text):
        return out
    if instinct:
        bad = [m for m in ("Option A", "My suggestion", "➡️") if m in text]
        out["instinct-first-pure"] = ("fail", "shows " + ", ".join(bad)) if bad else ("pass", "")
    else:
        opts = "Option A" in text and "Option B" in text
        out["two-options"] = ("pass", "") if opts else ("fail", "needs Option A and Option B")
        costs = UNDO.findall(text)
        out["undo-cost"] = ("pass", "") if len(costs) >= 2 else ("fail", f"{len(costs)} valid 'Undo cost:' values")
        out["against-line"] = ("pass", "") if "Against my suggestion" in text else ("fail", "no 'Against my suggestion'")
        conf = CONFIDENCE.search(text)
        if not conf:
            out["calibration"] = ("fail", "no 'Confidence:'")
        elif conf.group(1).lower() not in ("low", "medium", "high"):
            out["calibration"] = ("fail", f"confidence '{conf.group(1)}' is not low|medium|high")
        else:
            missing = [f for f in ("Checked:", "Inference:", "Assumptions:", "I would change my suggestion if:", "Not checked:", "Proposed number:") if f not in text]
            out["calibration"] = ("fail", "missing " + ", ".join(missing)) if missing else ("pass", "")
    ids = re.findall(r"\bQ\d+\b", text)
    out["names-not-ids"] = ("fail", "uses " + ", ".join(sorted(set(ids)))) if ids else ("pass", "")
    out["single-question"] = ("fail", f"{text.count(chr(0x2753))} question markers") if text.count("❓") > 1 else ("pass", "")
    words = len(text.split())
    out["length"] = ("fail", f"{words} words (limit 450, the checker's number)") if words > 450 else ("pass", f"{words} words")
    return out


def read_turns(path, since=None):
    """Yield (timestamp, kind, text) for assistant chat text and SendMessage bodies."""
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant" or (since and str(entry.get("timestamp", "")) < since):
            continue
        content = (entry.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if block.get("type") == "text":
                yield entry.get("timestamp", ""), "user-facing", block.get("text", "")
            elif block.get("type") == "tool_use" and block.get("name") == "SendMessage":
                yield entry.get("timestamp", ""), "sent:" + str((block.get("input") or {}).get("to", "")), (block.get("input") or {}).get("message", "")


# ---------- ledgers ----------
QUOTED = re.compile(r"[\"\u201c][^\"\u201d]{2,}[\"\u201d]|'[^']{3,}'")
TURN = re.compile(r"\bturn\s*\d+", re.I)


def cites_user_words(source, authority):
    """A user answer may quote the words or cite the turn; a delegation or simulated answer must quote."""
    if QUOTED.search(source):
        return True
    return authority == "user" and bool(TURN.search(source))


def ledger_findings(directory):
    sys.path.insert(0, str(SKILL_SCRIPTS))
    import session  # the real validator
    out = {}
    try:
        ledger = session.load(directory)
    except (ValueError, OSError, KeyError) as error:
        return {"valid-ledger": ("fail", str(error)[:120])}
    out["valid-ledger"] = ("pass", "")
    decisions = [n for n in ledger["nodes"] if n["kind"] == "decision" and n["id"] != ledger.get("origin") and n["status"] == "settled"]
    unsupported = [n["id"] for n in decisions if not cites_user_words(n.get("authority_source") or "", n["authority"])]
    out["source-cites-user-words"] = ("fail", "source neither quotes words nor cites a turn: " + ", ".join(unsupported)) if unsupported else ("pass", "")
    if decisions:
        accepted = sum(n["authority"] == "delegated" for n in decisions)
        rate = accepted / len(decisions)
        out["accept-rate"] = ("fail", f"{accepted}/{len(decisions)} accepted as suggested (>= 70%)") if rate >= 0.7 and len(decisions) >= 3 else ("pass", f"{accepted}/{len(decisions)}")
    else:
        out["accept-rate"] = ("na", "no settled decisions")
    return out


# ---------- contracts ----------
MAP_PARTS = (("what we know", "What we know"), ("we know we don't know", "What we know we don't know"),
             ("we have not read", "What we have not read"), ("could surprise us", "What could surprise us"))


def knowledge_map_finding(text):
    """The unknowns section must exist, be complete, and show real probes (not just reassurance)."""
    if not re.search(r"(?im)^#+\s*Knowledge map", text):
        return ("fail", "no 'Knowledge map' section")
    lower = text.lower()
    problems = [f"missing part '{label}'" for key, label in MAP_PARTS if key not in lower]
    probes = re.findall(r"(?m)^\W*Probe:.*$", text)
    if len(probes) < 3:
        problems.append(f"{len(probes)} Probe lines (need 3)")
    for line in probes:
        if "skipped by the user" in line:
            continue
        if "answer:" not in line or "changed:" not in line:
            problems.append("a Probe line lacks 'answer:' or 'changed:'")
            break
    look = re.search(r"(?m)^\W*Where we did not look:[ \t]*(\S.{2,})$", text)
    if not look:
        problems.append("no 'Where we did not look:' line with content")
    if "would know we were wrong if" not in lower:
        problems.append("no 'We would know we were wrong if:' signal")
    return ("fail", "; ".join(problems)) if problems else ("pass", f"{len(probes)} probes")


def contract_findings(path):
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    out = {}
    simulated = ".simulated." in path.name
    has_status = "simulated — not confirmed by a human" in text
    out["simulated-labelled"] = ("pass", "") if simulated == has_status else ("fail", "file name and status disagree about being simulated")
    out["confirming-box"] = ("pass", "") if "You are confirming" in text else ("fail", "no 'You are confirming' box")
    out["knowledge-map"] = knowledge_map_finding(text)
    m = re.search(r"(?ms)^## Acceptance checks[^\n]*\n(.*?)(?=^## |\Z)", text)
    if not m:
        out["check-lines"] = ("fail", "no Acceptance checks section")
        return out
    body = m.group(1)
    items = re.split(r"(?m)^(?=(?:[A-Z]\d+\b|\d+\.\s))", body)
    problems, checked = [], 0
    for item in (i for i in items if re.match(r"(?:[A-Z]\d+\b|\d+\.\s)", i)):
        if re.search(r"human[- ]only|\[user\] open the page", item, re.I):
            continue
        checked += 1
        missing = [k for k in ("cmd: `", "expect:", "cwd:") if k not in item]
        if missing:
            problems.append(f"{item.strip().splitlines()[0][:40]!r} missing {', '.join(missing)}")
    if checked == 0:
        out["check-lines"] = ("na", "no machine checks")
    else:
        out["check-lines"] = ("fail", "; ".join(problems)) if problems else ("pass", f"{checked} checks")
    return out


# ---------- reporting ----------
def summarize(rows):
    table = {}
    for _, results in rows:
        for rule, (status, _) in results.items():
            table.setdefault(rule, {"pass": 0, "fail": 0, "na": 0})[status] += 1
    return table


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="group", required=True)
    turns = sub.add_parser("turns")
    turns.add_argument("transcript", type=Path)
    turns.add_argument("--since", help="only turns at or after this ISO timestamp")
    turns.add_argument("--show-fails", action="store_true")
    turns.add_argument("--operators", help="comma-separated agent ids that are simulated operators (leak rule applies to messages sent to them)")
    ledgers = sub.add_parser("ledgers")
    ledgers.add_argument("root", type=Path, nargs="?", default=Path("~/.local/share/seed-me/sessions").expanduser())
    contracts = sub.add_parser("contracts")
    contracts.add_argument("files", type=Path, nargs="+")
    for p in (turns, ledgers, contracts):
        p.add_argument("--strict", action="store_true", help="exit 1 if any check fails")
    args = parser.parse_args()
    rows = []
    if args.group == "turns":
        operators = set(filter(None, (args.operators or "").split(",")))
        for stamp, kind, text in read_turns(args.transcript, args.since):
            to_operator = kind.startswith("sent:") and kind[5:] in operators
            if to_operator or is_question_turn(text):
                label = "operator" if to_operator else kind
                rows.append((f"{stamp[:19]} {label}: {text.strip().splitlines()[0][:50] if text.strip() else ''}", turn_findings(text, to_operator)))
    elif args.group == "ledgers":
        rows = [(d.parent.name[:8], ledger_findings(d.parent)) for d in sorted(args.root.glob("*/ledger.json"))]
    else:
        rows = [(f.name, contract_findings(f)) for f in args.files]
    table = summarize(rows)
    print(f"{args.group}: {len(rows)} items")
    for rule, counts in sorted(table.items()):
        print(f"  {rule:<22} pass {counts['pass']:>3}  fail {counts['fail']:>3}  n/a {counts['na']:>3}")
    show = getattr(args, "show_fails", False) or args.group != "turns"
    if show:
        for label, results in rows:
            for rule, (status, detail) in results.items():
                if status == "fail":
                    print(f"  FAIL {label} [{rule}] {detail}")
    if args.strict and any(s == "fail" for _, r in rows for s, _ in r.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
