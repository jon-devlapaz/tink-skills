import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import tempfile
import uuid


STATE_FIELDS = {"status", "draft", "goal", "origin", "current_question", "nodes"}
NODE_FIELDS = {"id", "kind", "status", "prerequisites", "predicate", "evidence",
               "answer", "authority", "authority_source", "label", "question",
               "owner", "gate", "recommendation", "defer_reason", "revisit_condition", "reopen_reason"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def now():
    return datetime.now(timezone.utc).isoformat()


def editable(ledger):
    state = {key: deepcopy(ledger[key]) for key in STATE_FIELDS}
    for node in state["nodes"]:
        node.pop("history", None)
        node.pop("revision", None)
    return state


def validate(state):
    require(isinstance(state, dict) and set(state) == STATE_FIELDS, "invalid session fields")
    require(state["status"] in ("active", "stopped", "completed"), "invalid session status")
    draft = state["draft"]
    require(isinstance(draft, dict) and set(draft) == {"goal", "outcome", "options"}, "invalid draft")
    require(isinstance(draft["goal"], str) and isinstance(draft["outcome"], str), "invalid draft text")
    require(isinstance(draft["options"], list) and all(text(v) for v in draft["options"]), "invalid draft options")
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
        require(isinstance(evidence, list) and all(text(e) for e in evidence), "invalid evidence")
        if node["kind"] == "decision":
            require(text(node.get("owner")) and text(node.get("gate")), "decision requires owner and gate")
        if node["status"] == "settled":
            require(text(node.get("answer")), "settled node requires answer")
            require(text(node.get("authority_source")), "settled node requires authority source")
            expected = ("evidence",) if node["kind"] == "fact" else ("user", "delegated")
            require(node.get("authority") in expected, "authority does not match node kind")
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
                and root["authority"] == "user" and root["answer"] == state["goal"],
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


def transition(ledger, state, expected_version, reason, revalidated=None):
    state = deepcopy(state)
    ready = validate(state)
    old_state = editable(ledger)
    require(type(expected_version) is int and expected_version >= 0, "invalid expected version")
    if state == old_state and expected_version <= ledger["version"]:
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
    premise_fields = ("status", "answer", "authority", "authority_source", "evidence", "prerequisites", "predicate", "question", "owner", "gate")
    changed = {key for key, node in old.items() if node["status"] == "settled"
               and any(node.get(f) != new[key].get(f) for f in premise_fields)}
    affected = set()
    for node_id in changed:
        affected |= descendants(list(old.values()), {node_id}) | descendants(list(new.values()), {node_id})
    revalidated = {} if revalidated is None else revalidated
    require(isinstance(revalidated, dict) and set(revalidated) <= affected, "invalid revalidation targets")
    for node_id in affected:
        if new[node_id]["status"] == "settled":
            require(text(revalidated.get(node_id)) and bool(new[node_id]["evidence"]),
                    "affected settlement requires explicit revalidation with evidence: " + node_id)
    revision = ledger["revision"] + bool(changed)
    updated = now()
    result = {**deepcopy(ledger), **state, "version": ledger["version"] + 1,
              "revision": revision, "updated_at": updated, "frontier": ready}
    old_stored = {n["id"]: n for n in ledger["nodes"]}
    for node in result["nodes"]:
        previous = old_stored.get(node["id"])
        history = deepcopy(previous["history"]) if previous else []
        material_change = previous is not None and (old[node["id"]] != node or node["id"] in revalidated)
        if material_change:
            history.append({"state": {k: deepcopy(v) for k, v in previous.items() if k != "history"},
                            "superseded_at": updated, "reason": revalidated.get(node["id"], reason)})
        node["history"] = history
        node["revision"] = revision if previous is None or material_change else previous["revision"]
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


def create(root=None):
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
              "origin": None, "current_question": None, "frontier": [], "nodes": []}
    atomic_write(directory / "ledger.json", ledger)
    return directory


def load(directory):
    ledger = json.loads((Path(directory) / "ledger.json").read_text())
    require(isinstance(ledger, dict) and type(ledger.get("schema_version")) is int
            and ledger["schema_version"] == 1, "unsupported ledger schema")
    require(set(ledger) == STATE_FIELDS | {"schema_version", "session_id", "version", "revision",
                                         "created_at", "updated_at", "frontier"}, "invalid stored ledger fields")
    require(text(ledger.get("session_id")), "missing session identity")
    for field in ("version", "revision"):
        require(type(ledger.get(field)) is int and ledger[field] >= 0, "invalid " + field)
    for node in ledger.get("nodes", []):
        require(isinstance(node, dict) and isinstance(node.get("history"), list), "missing node history")
        require(type(node.get("revision")) is int and 0 <= node["revision"] <= ledger["revision"], "invalid node revision")
        for entry in node["history"]:
            require(isinstance(entry, dict) and set(entry) == {"state", "superseded_at", "reason"}
                    and text(entry["reason"]) and text(entry["superseded_at"]), "invalid history entry")
            prior = entry["state"]
            require(isinstance(prior, dict) and not set(prior) - (NODE_FIELDS | {"revision"})
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
        return result


def end(directory, status, reason):
    require(status in ("stopped", "completed"), "invalid end status")
    directory = Path(directory)
    with writer(directory):
        ledger = load(directory)
        require(ledger["status"] in ("active", status), "ended session is read-only")
        state = editable(ledger)
        state.update(status=status, current_question=None)
        result = transition(ledger, state, ledger["version"], reason)
        if result is not ledger:
            atomic_write(directory / "ledger.json", result)
        return result


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init").add_argument("--root", type=Path)
    commands.add_parser("read").add_argument("session", type=Path)
    update = commands.add_parser("publish")
    update.add_argument("session", type=Path)
    update.add_argument("input", type=Path)
    finish = commands.add_parser("end")
    finish.add_argument("session", type=Path)
    finish.add_argument("--status", choices=("stopped", "completed"), required=True)
    finish.add_argument("--reason", required=True)
    args = parser.parse_args()
    try:
        if args.command == "init":
            result = {"session": str(create(args.root))}
        elif args.command == "read":
            result = load(args.session)
        elif args.command == "end":
            result = end(args.session, args.status, args.reason)
        else:
            payload = json.loads(args.input.read_text())
            result = publish(args.session, **payload)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
