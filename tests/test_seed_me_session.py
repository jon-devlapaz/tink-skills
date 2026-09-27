import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "skills/seed-me/scripts/session.py"
SPEC = importlib.util.spec_from_file_location("seed_session", SCRIPT)
session = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(session)


def node(node_id, kind="decision", parents=(), answer=None):
    result = {"id": node_id, "kind": kind, "status": "unresolved",
              "prerequisites": list(parents), "evidence": []}
    if kind == "decision":
        result.update(owner="project owner", gate="choose an option")
    if answer is not None:
        result.update(status="settled", answer=answer,
                      authority="evidence" if kind == "fact" else "user",
                      authority_source="observed source:1" if kind == "fact" else "chat: explicit answer",
                      evidence=["import.py:10: replace(existing)"] if kind == "fact" else [])
    return result


class TestSeedSession(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = session.create(self.root)

    def publish(self, state, reason="User confirmed goal and investigation scope", **kwargs):
        version = session.load(self.directory)["version"]
        return session.publish(self.directory, state, version, reason, **kwargs)

    def confirmed(self):
        state = session.editable(session.load(self.directory))
        state.update(goal="Recover Groveboard data", origin="goal")
        state["draft"] = {"goal": "Recover Groveboard data", "outcome": "Recover a backup",
                          "options": ["Export and import JSON", "Export first"]}
        state["nodes"] = [node("goal", answer=state["goal"])]
        return self.publish(state)

    def scenario(self):
        state = session.editable(self.confirmed())
        state["nodes"] += [node("import-behavior", "fact", answer="Imports replace existing data"),
                           node("backup", parents=["import-behavior"], answer="Require backup before import"),
                           node("button-label", answer="Import backup")]
        return self.publish(state, "Observed replace semantics; user chose backup requirement and label")

    def revised(self, ledger):
        state = session.editable(ledger)
        fact, backup = state["nodes"][1:3]
        fact.update(answer="Imports merge data", evidence=["import.py:10: merge(existing, incoming)"],
                    authority_source="direct read import.py:10")
        backup.update(status="unresolved")
        for key in ("answer", "authority", "authority_source"):
            backup.pop(key)
        state["current_question"] = "backup"
        return state

    def test_initial_draft_is_not_an_accepted_goal(self):
        ledger = session.load(self.directory)
        self.assertEqual((ledger["status"], ledger["origin"], ledger["goal"], ledger["nodes"], ledger["frontier"]),
                         ("active", None, None, [], []))
        state = session.editable(ledger)
        state["draft"]["goal"] = "Maybe backups"
        saved = self.publish(state, "Shape provisional draft")
        self.assertEqual(saved["draft"]["goal"], "Maybe backups")
        self.assertEqual((saved["origin"], saved["nodes"], saved["revision"], saved["version"]), (None, [], 0, 1))
        self.assertEqual(self.directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual((self.directory / "ledger.json").stat().st_mode & 0o777, 0o600)

    def test_confirming_goal_does_not_accept_draft_options(self):
        ledger = self.confirmed()
        self.assertEqual(ledger["origin"], "goal")
        self.assertEqual([(n["id"], n["answer"]) for n in ledger["nodes"]], [("goal", "Recover Groveboard data")])
        self.assertEqual(ledger["draft"]["options"], ["Export and import JSON", "Export first"])

    def test_premise_change_reopens_dependent_preserves_independent_and_history(self):
        before = self.scenario()
        saved = self.publish(self.revised(before), "Import implementation changed from replace to merge")
        self.assertEqual((saved["revision"], saved["frontier"], saved["current_question"]), (1, ["backup"], "backup"))
        backup = saved["nodes"][2]
        self.assertEqual(backup["status"], "unresolved")
        self.assertNotIn("answer", backup)
        self.assertEqual(backup["history"][0]["state"]["answer"], "Require backup before import")
        self.assertEqual(backup["history"][0]["state"]["authority"], "user")
        self.assertEqual(backup["history"][0]["reason"], "Import implementation changed from replace to merge")
        self.assertEqual(saved["nodes"][1]["history"][0]["state"]["evidence"], ["import.py:10: replace(existing)"])
        self.assertEqual(saved["nodes"][3], before["nodes"][3])
        self.assertEqual(session.load(self.directory), saved)

    def test_affected_answer_cannot_silently_survive(self):
        before = self.scenario()
        state = self.revised(before)
        state["nodes"][2] = session.editable(before)["nodes"][2]
        state["current_question"] = None
        with self.assertRaisesRegex(ValueError, "explicit revalidation"):
            self.publish(state, "Changed import semantics")
        self.assertEqual(session.load(self.directory), before)
        state["nodes"][2]["evidence"] = ["import.py:12: merge overwrites colliding keys"]
        saved = self.publish(state, "Changed import semantics", revalidated={"backup": "Backup still protects overwritten keys"})
        self.assertEqual(saved["nodes"][2]["answer"], "Require backup before import")
        self.assertEqual(saved["nodes"][2]["history"][0]["reason"], "Backup still protects overwritten keys")

    def test_retry_is_a_noop_but_stale_different_update_is_rejected(self):
        before = self.scenario()
        state = self.revised(before)
        saved = self.publish(state, "Changed import semantics")
        retried = session.publish(self.directory, state, before["version"], "Changed import semantics")
        self.assertEqual(retried, saved)
        state["draft"]["outcome"] = "A competing stale edit"
        with self.assertRaisesRegex(ValueError, "stale publication"):
            session.publish(self.directory, state, before["version"], "Competing edit")
        self.assertEqual(session.load(self.directory), saved)

    def test_cycles_and_missing_prerequisites_leave_file_unchanged(self):
        before = self.confirmed()
        for additions, message in [([node("a", parents=["b"]), node("b", parents=["a"])], "cycle"),
                                   ([node("a", parents=["missing"])], "missing prerequisite")]:
            with self.subTest(message=message):
                state = session.editable(before)
                state["nodes"] += additions
                with self.assertRaisesRegex(ValueError, message):
                    self.publish(state)
                self.assertEqual(session.load(self.directory), before)

    def test_graph_edges_are_not_required_for_independent_nodes(self):
        state = session.editable(self.confirmed())
        state["nodes"] += [node("a"), node("b", parents=["a"])]
        state["current_question"] = "a"
        saved = self.publish(state)
        self.assertEqual(saved["frontier"], ["a"])
        state["current_question"] = "b"
        with self.assertRaisesRegex(ValueError, "ready decision"):
            self.publish(state)
        state["current_question"] = "a"
        state["nodes"][1]["status"] = "deferred"
        state["nodes"][1].update(defer_reason="Not needed in first release", revisit_condition="Scope expands")
        state["current_question"] = None
        saved = self.publish(state)
        self.assertEqual(saved["frontier"], [])
        state["status"] = "completed"
        with self.assertRaisesRegex(ValueError, "unresolved"):
            self.publish(state)

    def test_node_removal_origin_change_and_history_injection_are_rejected(self):
        before = self.scenario()
        state = session.editable(before)
        state["nodes"].pop()
        with self.assertRaisesRegex(ValueError, "supersede instead"):
            self.publish(state)
        state = session.editable(before)
        state["goal"] = "An unrelated project"
        state["nodes"][0]["answer"] = state["goal"]
        with self.assertRaisesRegex(ValueError, "cannot be replaced"):
            self.publish(state)
        state = session.editable(before)
        state["nodes"][0]["history"] = []
        with self.assertRaisesRegex(ValueError, "node fields"):
            self.publish(state)
        self.assertEqual(session.load(self.directory), before)

    def test_transitive_dependents_cannot_keep_stale_answers(self):
        before = self.scenario()
        state = session.editable(before)
        state["nodes"].append(node("recovery-copy", parents=["backup"], answer="Make recovery prominent"))
        before = self.publish(state)
        state = self.revised(before)
        with self.assertRaisesRegex(ValueError, "unsettled prerequisites"):
            self.publish(state, "Changed import semantics")
        state["nodes"][-1] = node("recovery-copy", parents=["backup"])
        saved = self.publish(state, "Changed import semantics")
        self.assertEqual(saved["frontier"], ["backup"])
        self.assertEqual(saved["nodes"][-1]["history"][0]["state"]["answer"], "Make recovery prominent")

    def test_unknown_predicate_is_parked(self):
        state = session.editable(self.confirmed())
        state["nodes"].append({**node("conditional"), "predicate": None})
        self.assertEqual(self.publish(state)["frontier"], [])
        state["nodes"][-1]["predicate"] = True
        self.assertEqual(self.publish(state)["frontier"], ["conditional"])

    def test_rejects_false_authority_and_unconfirmed_nodes(self):
        state = session.editable(session.load(self.directory))
        state["nodes"] = [node("made-up-goal", answer="Buy servers")]
        with self.assertRaisesRegex(ValueError, "unconfirmed draft"):
            self.publish(state)
        state = session.editable(self.confirmed())
        state["nodes"].append(node("fact", "fact", answer="Observed"))
        state["nodes"][-1]["authority"] = "user"
        with self.assertRaisesRegex(ValueError, "authority"):
            self.publish(state)

    def test_stopped_session_preserves_blockers_and_is_read_only(self):
        state = session.editable(self.confirmed())
        state["nodes"].append(node("pending"))
        state["status"] = "stopped"
        stopped = self.publish(state, "User stopped interview")
        self.assertEqual(stopped["nodes"][-1]["status"], "unresolved")
        state["status"] = "active"
        with self.assertRaisesRegex(ValueError, "read-only"):
            self.publish(state, "Attempt implicit resumption")
        self.assertEqual(session.load(self.directory), stopped)

    def test_failed_atomic_replace_retains_last_good_ledger(self):
        before = self.confirmed()
        state = session.editable(before)
        state["draft"]["outcome"] = "New draft description"
        with patch.object(session.os, "replace", side_effect=OSError("disk failure")):
            with self.assertRaisesRegex(OSError, "disk failure"):
                self.publish(state)
        self.assertEqual(session.load(self.directory), before)
        self.assertEqual(list(self.directory.glob(".ledger-*.tmp")), [])
        self.assertEqual(self.publish(state)["draft"]["outcome"], "New draft description")

    def test_second_writer_is_rejected_and_lock_releases(self):
        state = session.editable(session.load(self.directory))
        state["draft"]["goal"] = "Backups"
        with session.writer(self.directory):
            with self.assertRaisesRegex(ValueError, "already has a writer"):
                self.publish(state)
        self.assertEqual(self.publish(state)["draft"]["goal"], "Backups")

    def test_corrupt_frontier_is_not_silently_accepted(self):
        before = self.confirmed()
        before["frontier"] = ["goal"]
        (self.directory / "ledger.json").write_text(json.dumps(before))
        with self.assertRaisesRegex(ValueError, "frontier"):
            session.load(self.directory)

    def test_session_isolation_and_repository_boundary(self):
        other = session.create(self.root)
        self.assertNotEqual(other, self.directory)
        self.confirmed()
        self.assertEqual(session.load(other)["nodes"], [])
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside a repository"):
            session.create(repo / "sessions")
        self.assertFalse((repo / "sessions").exists())

    def test_cli_roundtrip_and_invalid_publication(self):
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
        initialized = run("init", "--root", self.root)
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        directory = Path(json.loads(initialized.stdout)["session"])
        ledger = json.loads(run("read", directory).stdout)
        state = session.editable(ledger)
        state["draft"]["goal"] = "Recover data"
        payload = self.root / "update.json"
        payload.write_text(json.dumps({"state": state, "expected_version": 0, "reason": "Draft shaped"}))
        result = run("publish", directory, payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["draft"]["goal"], "Recover data")
        self.assertEqual(json.loads(run("read", directory).stdout)["version"], 1)
        payload.write_text('{}')
        failed = run("publish", directory, payload)
        self.assertEqual(failed.returncode, 1)
        self.assertTrue(failed.stderr)
        self.assertEqual(json.loads(run("read", directory).stdout)["version"], 1)


if __name__ == "__main__":
    unittest.main()
