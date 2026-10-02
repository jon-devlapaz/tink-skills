import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from urllib.request import urlopen


STATE_FIELDS = {"status", "draft", "goal", "origin", "current_question", "nodes"}
OPTIONAL_STATE_FIELDS = {"assumed", "operator"}
OPERATORS = ("human", "simulated")
NODE_FIELDS = {"id", "kind", "status", "prerequisites", "predicate", "evidence",
               "answer", "authority", "authority_source", "label", "question",
               "owner", "gate", "recommendation", "defer_reason", "revisit_condition", "reopen_reason", "contradicts",
               "claim", "supported_by", "rationale"}
CLAIM_TYPES = ("observation", "inference", "unknown")
CLAIM_FIELDS = {"type", "scope", "limits"}
RATIONALE_FIELDS = {"feasibility", "intent"}
RECEIPT_FIELDS = {"checked", "at", "observed", "check", "artifact"}
# Helper-owned, never published. premise_version: the publication that last changed what a node records as evidence.
# reviewed_version: the publication that last reviewed what the node relies on. Labels, questions and owners move neither.
HELPER_NODE_FIELDS = ("revision", "premise_version", "reviewed_version")
EVIDENCE_FIELDS = ("status", "answer", "evidence", "claim", "supported_by")
# A best-effort backstop for the rule "no secrets in receipts"; the rule itself is the host's to keep.
SECRET = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{20,}"
                    r"|\bsk-[A-Za-z0-9_-]{20,}|\bxox[abprs]-[A-Za-z0-9-]{10,}|://[^/\s:@]+:[^/\s@]+@"
                    r"|\b(?:password|passwd|secret|token|api[_-]?key)\s*=\s*\S{6,}|\bbearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def now():
    return datetime.now(timezone.utc).isoformat()


def validate_receipt(receipt):
    """A receipt records what was checked, when, and what was observed. `check` and `artifact` are stored, never run."""
    require(isinstance(receipt, dict) and {"checked", "at", "observed"} <= set(receipt) <= RECEIPT_FIELDS
            and all(text(v) for v in receipt.values()),
            "invalid receipt: checked, at, and observed are required; check and artifact are optional; all non-blank strings")
    try:
        when = datetime.fromisoformat(receipt["at"].strip().replace("Z", "+00:00"))
    except ValueError:
        when = None
    require(when is not None and when.tzinfo is not None, "invalid receipt time: an ISO 8601 timestamp with a UTC offset")
    require(not any(SECRET.search(v) for v in receipt.values()), "receipt appears to contain a secret: record where it lives, never its value")


def validate_claim(node):
    claim = node["claim"]
    require(node["kind"] == "fact", "claim is only allowed on a fact: a decision is settled by authority, not evidence")
    require(isinstance(claim, dict) and claim.get("type") in CLAIM_TYPES and set(claim) <= CLAIM_FIELDS,
            "invalid claim: type is observation, inference, or unknown, with scope and optional limits")
    require(text(claim.get("scope")), "claim requires a scope: what was examined, or what the claim covers")
    require("limits" not in claim or text(claim["limits"]), "invalid claim limits")
    if claim["type"] == "inference":
        require(text(claim.get("limits")), "an inference must state its limits: what it does not establish")
        require(bool(node.get("supported_by")), "an inference must cite the observations that support it")


def validate_support(node, nodes):
    support = node["supported_by"]
    require(isinstance(support, list) and bool(support) and all(text(s) for s in support) and len(set(support)) == len(support),
            "invalid supported_by: distinct node IDs")
    claim = node.get("claim")
    require(node["kind"] == "decision" or (claim or {}).get("type") == "inference",
            "supported_by is only allowed on a decision or an inference: an observation is checked directly and an unknown has no support")
    for source in support:
        require(source in nodes and source != node["id"], "supported_by must name another node")
        found = nodes[source]
        found_type = (found.get("claim") or {}).get("type")
        require(found["kind"] == "fact" and found_type != "unknown",
                "supported_by must name a fact that records evidence, not a decision or an unknown")
        require(claim is None or found_type == "observation", "an inference is supported by observations, not by other inferences")


def validate_rationale(node):
    rationale = node["rationale"]
    require(node["kind"] == "decision", "rationale is only allowed on a decision")
    require(isinstance(rationale, dict) and bool(rationale) and set(rationale) <= RATIONALE_FIELDS
            and all(text(v) for v in rationale.values()),
            "invalid rationale: feasibility (what the current architecture allows) and/or intent (the user's outcome or threat model), non-blank")


def editable(ledger):
    state = {key: deepcopy(ledger[key]) for key in STATE_FIELDS}
    state["assumed"] = deepcopy(ledger.get("assumed", []))
    state["operator"] = ledger.get("operator", "human")
    for node in state["nodes"]:
        node.pop("history", None)
        for field in HELPER_NODE_FIELDS:
            node.pop(field, None)
    return state


def validate(state):
    require(isinstance(state, dict) and STATE_FIELDS <= set(state) <= STATE_FIELDS | OPTIONAL_STATE_FIELDS, "invalid session fields")
    operator = state.get("operator", "human")
    require(operator in OPERATORS, "invalid operator: human or simulated")
    assumed = state.get("assumed", [])
    require(isinstance(assumed, list) and all(isinstance(a, dict) and set(a) == {"text", "why"} and text(a["text"]) and text(a["why"]) for a in assumed),
            "invalid assumed: a list of {\"text\", \"why\"} entries with non-blank strings")
    require(state["status"] in ("active", "stopped", "completed"), "invalid session status")
    draft = state["draft"]
    require(isinstance(draft, dict) and set(draft) == {"goal", "outcome", "options"}, "invalid draft")
    require(isinstance(draft["goal"], str) and isinstance(draft["outcome"], str), "invalid draft text")
    require(isinstance(draft["options"], list) and all(text(v) for v in draft["options"]), "invalid draft options: each option must be a non-empty string such as 'Label — tradeoff'")
    require(isinstance(state["nodes"], list), "nodes must be a list")
    nodes = {}
    for node in state["nodes"]:
        require(isinstance(node, dict) and not set(node) - NODE_FIELDS, "invalid node fields")
        require(text(node.get("id")), "node requires an id")
        require(node["id"] not in nodes, "duplicate node id")
        nodes[node["id"]] = node
        require(node.get("kind") in ("fact", "decision"), "invalid node kind")
        require(node.get("status") in ("unresolved", "settled", "deferred", "superseded"), "invalid node status")
        prerequisites = node.get("prerequisites")
        require(isinstance(prerequisites, list) and all(text(p) for p in prerequisites), "invalid prerequisites")
        require(len(set(prerequisites)) == len(prerequisites), "duplicate prerequisite")
        require(node.get("predicate", True) is None or type(node.get("predicate", True)) is bool,
                "predicate must be an observed boolean or unknown (null)")
        evidence = node.get("evidence")
        require(isinstance(evidence, list) and all(text(e) or isinstance(e, dict) for e in evidence), "invalid evidence")
        for entry in evidence:
            if isinstance(entry, dict):
                validate_receipt(entry)
        if node["kind"] == "decision":
            require(text(node.get("owner")) and text(node.get("gate")), "decision requires owner and gate")
        if node["status"] == "settled":
            require(text(node.get("answer")), "settled node requires answer")
            require(text(node.get("authority_source")), "settled node requires authority source")
            expected = ("evidence",) if node["kind"] == "fact" else (("simulated",) if operator == "simulated" else ("user", "delegated"))
            require(node.get("authority") in expected, "authority does not match node kind or operator: a simulated operator can only settle decisions as 'simulated', a human session never as 'simulated'")
            if node["authority"] in ("evidence", "delegated"):
                require(bool(evidence), "evidence or delegated settlement requires evidence")
        else:
            require(node.get("answer") is None and node.get("authority") is None
                    and node.get("authority_source") is None, "unsettled node cannot carry an active answer")
        if "reopen_reason" in node:
            require(text(node["reopen_reason"]), "invalid reopen reason")
        if node["status"] == "deferred":
            require(text(node.get("defer_reason")) and text(node.get("revisit_condition")),
                    "deferral requires reason and revisit condition")
    for node in nodes.values():
        if "claim" in node:
            validate_claim(node)
        if "supported_by" in node:
            validate_support(node, nodes)
        if "rationale" in node:
            validate_rationale(node)
    for node in nodes.values():
        if "contradicts" in node:
            target = node["contradicts"]
            require(node["kind"] == "fact" and text(target) and target != node["id"] and target in nodes,
                    "contradicts must name another node and is only allowed on a fact")
    visiting, visited = set(), set()

    def visit(node_id):
        require(node_id in nodes, "missing prerequisite")
        require(node_id not in visiting, "dependency cycle")
        if node_id in visited:
            return
        visiting.add(node_id)
        for parent in nodes[node_id]["prerequisites"]:
            visit(parent)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in nodes:
        visit(node_id)
    for node in nodes.values():
        if node["status"] == "settled":
            require(node.get("predicate", True) is True, "settled node has inactive or unknown predicate")
            require(all(nodes[p]["status"] == "settled" for p in node["prerequisites"]),
                    "settled node has unsettled prerequisites")
    origin = state["origin"]
    if origin is None:
        require(state["goal"] is None and not nodes, "unconfirmed draft cannot contain ledger nodes")
    else:
        require(text(origin) and origin in nodes and text(state["goal"]), "invalid confirmed goal")
        root = nodes[origin]
        require(root["kind"] == "decision" and root["status"] == "settled"
                and root["authority"] == ("simulated" if operator == "simulated" else "user") and root["answer"] == state["goal"],
                "origin requires an explicitly confirmed user goal")
    ready = [n["id"] for n in nodes.values() if n["status"] == "unresolved"
             and n.get("predicate", True) is True
             and all(nodes[p]["status"] == "settled" for p in n["prerequisites"])]
    current = state["current_question"]
    require(current is None or (current in ready and nodes[current]["kind"] == "decision"),
            "current question must be a ready decision")
    if state["status"] != "active":
        require(current is None, "ended session cannot have a current question")
    if state["status"] == "completed":
        require(origin is not None and all(n["status"] != "unresolved" for n in nodes.values()),
                "cannot complete with unresolved concerns")
    return ready


def descendants(nodes, starts):
    reached = set(starts)
    while True:
        added = {n["id"] for n in nodes if any(p in reached for p in n["prerequisites"])} - reached
        if not added:
            return reached - set(starts)
        reached.update(added)


def contradiction_blockers(nodes):
    """Settled decisions that a settled fact contradicts and that were not revisited since."""
    by_id = {n["id"]: n for n in nodes}
    blocked = []
    for fact in nodes:
        target = by_id.get(fact.get("contradicts"))
        if fact["status"] == "settled" and target and target["status"] == "settled" \
                and target["revision"] <= fact["revision"] and target["id"] not in blocked:
            blocked.append(target["id"])
    return blocked


def support_dependents(nodes, starts):
    """Nodes that rely on the starts as evidence (`supported_by`), transitively. Not the workflow order."""
    reached = set(starts)
    while True:
        added = {n["id"] for n in nodes if any(s in reached for s in n.get("supported_by", ()))} - reached
        if not added:
            return reached - set(starts)
        reached.update(added)


def evidence_differs(before, after):
    """Whether what a node records as evidence changed. Classifying a legacy entry (no claim yet) only labels it."""
    return any(before.get(f) != after.get(f) for f in EVIDENCE_FIELDS if not (f == "claim" and before.get(f) is None))


def review_flags(nodes):
    """Settled nodes that rely on evidence that changed, was withdrawn, or was contradicted since they were recorded.

    Derived and read-only: a flag asks for review. It never reopens a node, erases its answer or authority, or picks a replacement.
    """
    by_id = {n["id"]: n for n in nodes}
    contradicted = {f["contradicts"]: f for f in nodes if f["status"] == "settled" and f.get("contradicts")}
    flags = {}
    for node in nodes:
        if node["status"] != "settled":
            continue
        reviewed = node.get("reviewed_version", 0)
        for source in node.get("supported_by", ()):
            found = by_id[source]
            moved = found.get("premise_version", 1)
            if moved > reviewed:
                why = "withdrawn" if found["status"] != "settled" else "changed"
            elif found["status"] == "settled" and source in contradicted and moved <= contradicted[source].get("premise_version", 1) \
                    and contradicted[source].get("premise_version", 1) > reviewed:
                why = "contradicted"
            else:
                continue
            flags.setdefault(node["id"], []).append({"because": source, "why": why})
    grew = True
    while grew:
        grew = False
        for node in nodes:
            if node["status"] != "settled":
                continue
            for source in node.get("supported_by", ()):
                known = flags.get(node["id"], [])
                if source in flags and not any(f["because"] == source for f in known):
                    flags.setdefault(node["id"], []).append({"because": source, "why": "under review"})
                    grew = True
    return flags


def transition(ledger, state, expected_version, reason, revalidated=None):
    state = deepcopy(state)
    state.setdefault("assumed", [])
    state.setdefault("operator", ledger.get("operator", "human"))
    ready = validate(state)
    require(state["operator"] == ledger.get("operator", "human"), "operator cannot change in a session")
    old_state = editable(ledger)
    require(type(expected_version) is int and expected_version >= 0, "invalid expected version")
    # An exact repeat is a no-op, but a review of flagged nodes (revalidated) records a decision even when nothing else changed.
    if state == old_state and expected_version <= ledger["version"] and not (revalidated and expected_version == ledger["version"]):
        return ledger
    require(expected_version == ledger["version"], "stale publication version")
    require(ledger["status"] == "active", "ended session is read-only")
    require(text(reason), "update requires a reason")
    if ledger["origin"] is not None:
        require(state["origin"] == ledger["origin"] and state["goal"] == ledger["goal"],
                "confirmed origin and goal cannot be replaced in this session")
    old = {n["id"]: n for n in old_state["nodes"]}
    new = {n["id"]: n for n in state["nodes"]}
    require(set(old) <= set(new), "preserve nodes; supersede instead of deleting")
    for node_id in old:
        require(old[node_id]["kind"] == new[node_id]["kind"], "node kind is immutable")
        if old[node_id]["status"] == "settled" and new[node_id]["status"] == "unresolved":
            require(text(new[node_id].get("reopen_reason")), "reopened node requires a reopen reason")
    premise_fields = ("status", "answer", "authority", "authority_source", "evidence", "prerequisites", "predicate", "question", "owner", "gate",
                      "claim", "supported_by")
    # Classifying a legacy entry (no claim yet) labels it; it does not change what was recorded.
    changed = {key for key, node in old.items() if node["status"] == "settled"
               and any(node.get(f) != new[key].get(f) for f in premise_fields if not (f == "claim" and node.get(f) is None))}
    affected = set()
    for node_id in changed:
        affected |= descendants(list(old.values()), {node_id}) | descendants(list(new.values()), {node_id})
    revalidated = {} if revalidated is None else revalidated
    reviewable = affected | support_dependents(list(old.values()), changed) | support_dependents(list(new.values()), changed) \
        | set(review_flags(ledger["nodes"]))
    require(isinstance(revalidated, dict) and set(revalidated) <= reviewable, "invalid revalidation targets")
    require(all(text(v) for v in revalidated.values()), "revalidation requires a justification")
    for node_id in affected:
        if new[node_id]["status"] == "settled":
            require(text(revalidated.get(node_id)) and bool(new[node_id]["evidence"]),
                    "affected settlement requires explicit revalidation with evidence: " + node_id)
    assumed_changed = state["assumed"] != old_state["assumed"]
    revision = ledger["revision"] + bool(changed or assumed_changed)
    updated = now()
    result = {**deepcopy(ledger), **state, "version": ledger["version"] + 1,
              "revision": revision, "updated_at": updated, "frontier": ready}
    old_stored = {n["id"]: n for n in ledger["nodes"]}
    flagged_before = set(review_flags(ledger["nodes"]))
    for node in result["nodes"]:
        previous = old_stored.get(node["id"])
        history = deepcopy(previous["history"]) if previous else []
        material_change = previous is not None and (old[node["id"]] != node or node["id"] in revalidated)
        if material_change:
            history.append({"state": {k: deepcopy(v) for k, v in previous.items() if k != "history"},
                            "superseded_at": updated, "reason": revalidated.get(node["id"], reason)})
        node["history"] = history
        node["revision"] = revision if previous is None or material_change else previous["revision"]
        # Reviewing a node that was flagged is itself news for whatever relies on it: that node must be reviewed in its own right.
        moved = previous is None or evidence_differs(old[node["id"]], node) or (node["id"] in revalidated and node["id"] in flagged_before)
        # Settling on evidence that is not yet recorded is not a review; only an explicit revalidation is.
        grounded = all(new[s]["status"] == "settled" for s in node.get("supported_by", ()))
        implicit = previous is None or (previous["status"] != "settled" and node["status"] == "settled") \
            or previous.get("supported_by") != node.get("supported_by")
        reviewed = node["id"] in revalidated or (implicit and grounded)
        for field, now_moved in (("premise_version", moved), ("reviewed_version", reviewed)):
            if now_moved:
                node[field] = result["version"]
            elif previous is not None and field in previous:
                node[field] = previous[field]
            elif field == "reviewed_version":
                node[field] = 0
    if state["status"] == "completed":
        blocked = contradiction_blockers(result["nodes"])
        require(not blocked, "cannot complete: evidence contradicts a settled decision that was not revisited: " + ", ".join(blocked))
        flagged = sorted(review_flags(result["nodes"]))
        require(not flagged, "cannot complete: evidence behind these settled nodes changed, was withdrawn, or was contradicted "
                "and they were not reviewed (revalidate each with a reason; answers stay as they are): " + ", ".join(flagged))
    return result


def atomic_write(path, ledger):
    atomic_write_text(path, json.dumps(ledger, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def atomic_write_text(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=".ledger-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


ASSET = Path(__file__).resolve().parents[1] / "assets/ledger-view.html"
VENDOR = Path(__file__).resolve().parents[1] / "assets/vendor/cytoscape.min.js"
LIBRARY_TAG = re.compile(r'<script async id="graph-library"[^>]*></script>')
SNAPSHOT_MARKER = '{"__LEDGER_JSON__":true,"revision":0,"goal":null,"origin":null,"frontier":[],"nodes":[]}'


def snapshot_data(ledger):
    return json.dumps(ledger, ensure_ascii=True, allow_nan=False).replace("<", "\\u003c")


def snapshot_page(ledger):
    template = ASSET.read_text(encoding="utf-8")
    if template.count(SNAPSHOT_MARKER) != 1:
        raise ValueError("viewer template requires one snapshot marker")
    page = template.replace(SNAPSHOT_MARKER, snapshot_data(ledger))
    if VENDOR.is_file():
        # Self-contained: the graph library travels inside the page, so it works with no network.
        library = VENDOR.read_text(encoding="utf-8")
        require("</script" not in library.lower() and "<!--" not in library, "vendored library cannot be inlined")
        page, count = LIBRARY_TAG.subn(lambda _: '<script id="graph-library">' + library + "</script>", page, count=1)
        require(count == 1, "viewer template requires one graph-library tag")
    return page


def write_snapshot(directory):
    """Save the view next to the ledger. Callers hold the writer lock, so the view can never lag the ledger."""
    destination = Path(directory) / "ledger-view.html"
    require(not destination.is_symlink(), "viewer destination must not be a symlink")
    atomic_write_text(destination, snapshot_page(load(directory)))
    return destination


def viewer_record(directory):
    try:
        record = json.loads((Path(directory) / "viewer.json").read_text())
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def viewer_state(directory):
    record = viewer_record(directory)
    if record is None:
        return "not started"
    if record.get("declined"):
        return "declined: " + record["declined"]
    try:
        with urlopen(record["url"], timeout=1) as response:
            if response.status == 200:
                return "live " + record["url"]
    except (OSError, KeyError, ValueError):
        pass
    return "started earlier, not running now"


def status(directory):
    directory = Path(directory)
    ledger = load(directory)
    snapshot = directory / "ledger-view.html"
    current = snapshot.is_file() and snapshot_data(ledger) in snapshot.read_text(encoding="utf-8")
    nodes = ledger["nodes"]
    return {"status": ledger["status"], "revision": ledger["revision"], "version": ledger["version"],
            "open": sum(1 for n in nodes if n["status"] == "unresolved"),
            "settled": sum(1 for n in nodes if n["status"] == "settled"),
            "current_question": ledger["current_question"], "viewer": viewer_state(directory),
            "snapshot": str(snapshot), "snapshot_current": current}


def create(root=None, operator="human"):
    require(operator in OPERATORS, "invalid operator: human or simulated")
    root = Path(root) if root is not None else Path.home() / ".local/share/seed-me/sessions"
    root = root.expanduser().resolve()
    require(not any((p / ".git").exists() for p in (root, *root.parents)), "session storage must be outside a repository")
    root.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    directory = root / session_id
    directory.mkdir(mode=0o700)
    timestamp = now()
    ledger = {"schema_version": 1, "session_id": session_id, "version": 0, "revision": 0,
              "created_at": timestamp, "updated_at": timestamp, "status": "active",
              "draft": {"goal": "", "outcome": "", "options": []}, "goal": None,
              "origin": None, "current_question": None, "frontier": [], "nodes": [], "assumed": [], "operator": operator}
    atomic_write(directory / "ledger.json", ledger)
    write_snapshot(directory)
    return directory


def load(directory):
    ledger = json.loads((Path(directory) / "ledger.json").read_text())
    require(isinstance(ledger, dict) and type(ledger.get("schema_version")) is int
            and ledger["schema_version"] == 1, "unsupported ledger schema")
    require(set(ledger) == STATE_FIELDS | OPTIONAL_STATE_FIELDS | {"schema_version", "session_id", "version", "revision",
                                         "created_at", "updated_at", "frontier"}, "invalid stored ledger fields")
    require(text(ledger.get("session_id")), "missing session identity")
    for field in ("version", "revision"):
        require(type(ledger.get(field)) is int and ledger[field] >= 0, "invalid " + field)
    for node in ledger.get("nodes", []):
        require(isinstance(node, dict) and isinstance(node.get("history"), list), "missing node history")
        require(type(node.get("revision")) is int and 0 <= node["revision"] <= ledger["revision"], "invalid node revision")
        for field in HELPER_NODE_FIELDS[1:]:
            require(field not in node or (type(node[field]) is int and 0 <= node[field] <= ledger["version"]), "invalid node " + field)
        for entry in node["history"]:
            require(isinstance(entry, dict) and set(entry) == {"state", "superseded_at", "reason"}
                    and text(entry["reason"]) and text(entry["superseded_at"]), "invalid history entry")
            prior = entry["state"]
            require(isinstance(prior, dict) and not set(prior) - (NODE_FIELDS | set(HELPER_NODE_FIELDS))
                    and prior.get("id") == node["id"] and prior.get("kind") == node["kind"],
                    "invalid historical node")
    require(validate(editable(ledger)) == ledger.get("frontier"), "stored frontier is inconsistent")
    return ledger


@contextmanager
def writer(directory):
    with (Path(directory) / ".writer.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("session already has a writer") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def publish(directory, state, expected_version, reason, revalidated=None):
    directory = Path(directory)
    with writer(directory):
        ledger = load(directory)
        result = transition(ledger, state, expected_version, reason, revalidated)
        if result is not ledger:
            atomic_write(directory / "ledger.json", result)
        write_snapshot(directory)
        return result


def end(directory, status, reason, no_viewer=None):
    """Completing an active session needs the viewer: viewer.py was started, or no_viewer says why it could not be."""
    require(status in ("stopped", "completed"), "invalid end status")
    directory = Path(directory)
    with writer(directory):
        ledger = load(directory)
        require(ledger["status"] in ("active", status), "ended session is read-only")
        needs_viewer = status == "completed" and ledger["status"] == "active"
        if needs_viewer:
            if no_viewer is not None:
                require(no_viewer.strip(), "--no-viewer needs a reason")
            else:
                record = viewer_record(directory)
                require(record and record.get("pid"), "completion needs the viewer: start viewer.py, "
                        "or pass --no-viewer with the reason it could not run")
        state = editable(ledger)
        state.update(status=status, current_question=None)
        result = transition(ledger, state, ledger["version"], reason)
        if result is not ledger:
            atomic_write(directory / "ledger.json", result)
        if needs_viewer and no_viewer is not None:
            atomic_write_text(directory / "viewer.json", json.dumps({"declined": no_viewer.strip(), "at": now()}))
        write_snapshot(directory)
        return result


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--root", type=Path)
    init.add_argument("--operator", choices=OPERATORS, default="human")
    commands.add_parser("read").add_argument("session", type=Path)
    update = commands.add_parser("publish")
    update.add_argument("session", type=Path)
    update.add_argument("input", type=Path)
    finish = commands.add_parser("end")
    finish.add_argument("session", type=Path)
    finish.add_argument("--status", choices=("stopped", "completed"), required=True)
    finish.add_argument("--reason", required=True)
    finish.add_argument("--no-viewer", metavar="REASON", help="complete without a running viewer, stating why")
    commands.add_parser("status").add_argument("session", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = {"session": str(create(args.root, args.operator))}
        elif args.command == "read":
            result = load(args.session)
        elif args.command == "end":
            result = end(args.session, args.status, args.reason, args.no_viewer)
        elif args.command == "status":
            result = status(args.session)
        else:
            payload = json.loads(args.input.read_text())
            result = publish(args.session, **payload)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
