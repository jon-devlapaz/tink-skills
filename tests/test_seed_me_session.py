import importlib.util
import json
from pathlib import Path
import re
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
        backup.update(status="unresolved", reopen_reason="Import semantics changed from replace to merge")
        for key in ("answer", "authority", "authority_source"):
            backup.pop(key)
        state["current_question"] = "backup"
        return state

    def test_assumed_defaults_round_trip_and_never_become_answers(self):
        state = session.editable(session.load(self.directory))
        state["assumed"] = [{"text": "Local machine only", "why": "Both answers give the same build"}]
        result = self.publish(state, "Record a low-consequence default")
        self.assertEqual(result["assumed"], state["assumed"])
        self.assertEqual(session.load(self.directory)["assumed"], state["assumed"])
        self.assertEqual(result["nodes"], [])

    def test_assumed_rejects_malformed_entries(self):
        base = session.editable(session.load(self.directory))
        for bad in ("text", ["just a string"], [{"text": "x"}], [{"text": "x", "why": " "}],
                    [{"text": "x", "why": "y", "extra": "z"}], [{"text": 5, "why": "y"}]):
            with self.subTest(bad=bad):
                state = {**base, "assumed": bad}
                with self.assertRaisesRegex(ValueError, "invalid assumed"):
                    self.publish(state, "Bad assumption shape")

    def test_assumed_change_bumps_the_revision_and_a_repeat_is_a_noop(self):
        state = session.editable(session.load(self.directory))
        state["assumed"] = [{"text": "One machine", "why": "Both answers build the same tool"}]
        first = self.publish(state, "Record a default")
        self.assertEqual(first["revision"], 1)
        again = self.publish(state, "Record a default")
        self.assertEqual((again["version"], again["revision"]), (first["version"], 1))
        state["assumed"] = [{"text": "One machine", "why": "A different reason"}]
        self.assertEqual(self.publish(state, "Change the reason")["revision"], 2)
        state["assumed"] = []
        self.assertEqual(self.publish(state, "Drop the default")["revision"], 3)

    def contradicted_state(self, fact_status="settled"):
        state = session.editable(session.load(self.directory))
        state.update(goal="Ship it", origin="goal")
        fact = {**node("f", "fact", answer="The scanner does not exist"), "contradicts": "d"}
        if fact_status != "settled":
            fact = {**node("f", "fact"), "status": fact_status, "contradicts": "d"}
        state["nodes"] = [node("goal", answer="Ship it"),
                          node("d", parents=["goal"], answer="Reuse the existing scanner"), fact]
        return state

    def test_contradicting_fact_blocks_completion_until_the_decision_is_revisited(self):
        self.publish(self.contradicted_state())
        with self.assertRaisesRegex(ValueError, "contradicts a settled decision.*: d"):
            session.end(self.directory, "completed", "Confirmed and saved", no_viewer="not under test")
        state = session.editable(session.load(self.directory))
        state["nodes"][1]["answer"] = "Build the scanner as part of this work"
        self.publish(state, "Revise the decision after the contradicting evidence")
        self.assertEqual(session.end(self.directory, "completed", "Confirmed and saved", no_viewer="not under test")["status"], "completed")

    def test_superseding_the_contradicting_fact_also_unblocks_completion(self):
        self.publish(self.contradicted_state())
        state = session.editable(session.load(self.directory))
        state["nodes"][2] = {**node("f", "fact"), "status": "superseded", "contradicts": "d"}
        self.publish(state, "The fact was wrong; superseded with a reason")
        self.assertEqual(session.end(self.directory, "completed", "Confirmed and saved", no_viewer="not under test")["status"], "completed")

    def test_contradicts_shape_is_validated(self):
        base = self.contradicted_state()
        for label, mutate in (
                ("on a decision", lambda s: s["nodes"][1].update(contradicts="goal")),
                ("self reference", lambda s: s["nodes"][2].update(contradicts="f")),
                ("missing target", lambda s: s["nodes"][2].update(contradicts="nope")),
                ("not a string", lambda s: s["nodes"][2].update(contradicts=5))):
            with self.subTest(label):
                state = json.loads(json.dumps(base))
                mutate(state)
                with self.assertRaisesRegex(ValueError, "contradicts must name another node"):
                    self.publish(state, "Bad contradicts")

    def simulated_state(self, directory, authority="simulated", origin_authority="simulated"):
        state = session.editable(session.load(directory))
        goal_node = {**node("goal", answer="Ship it"), "authority": origin_authority}
        decision = {**node("d", parents=["goal"], answer="Do it"), "authority": authority,
                    "authority_source": "operator agent (persona: cautious): accepted the suggestion"}
        state.update(goal="Ship it", origin="goal", nodes=[goal_node, decision])
        return state

    def test_simulated_operator_settles_only_as_simulated(self):
        directory = session.create(self.root, "simulated")
        self.assertEqual(session.load(directory)["operator"], "simulated")
        state = self.simulated_state(directory)
        saved = session.publish(directory, state, 0, "Operator agent confirmed the goal")
        self.assertEqual(saved["nodes"][1]["authority"], "simulated")
        for label, bad in (("user decision", self.simulated_state(directory, authority="user")),
                           ("delegated decision", self.simulated_state(directory, authority="delegated")),
                           ("user goal", self.simulated_state(directory, origin_authority="user"))):
            with self.subTest(label), self.assertRaises(ValueError):
                fresh = session.create(self.root, "simulated")
                session.publish(fresh, {**bad, "operator": "simulated"}, 0, "Should be refused")

    def test_a_human_session_never_accepts_simulated_answers(self):
        state = self.simulated_state(self.directory)
        with self.assertRaisesRegex(ValueError, "authority does not match"):
            self.publish(state, "A human session cannot hold simulated answers")

    def test_operator_cannot_be_changed(self):
        directory = session.create(self.root, "simulated")
        state = session.editable(session.load(directory))
        state["operator"] = "human"
        with self.assertRaisesRegex(ValueError, "operator cannot change"):
            session.publish(directory, state, 0, "Attempt to launder a simulated session")
        with self.assertRaises(ValueError):
            session.create(self.root, "robot")

    def test_cli_init_can_start_a_simulated_session(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "init", "--root", str(self.root / "cli"),
                                 "--operator", "simulated"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        import json
        directory = json.loads(result.stdout)["session"]
        self.assertEqual(session.load(directory)["operator"], "simulated")

    def test_draft_options_error_says_options_are_plain_strings(self):
        state = session.editable(session.load(self.directory))
        state["draft"]["options"] = [{"label": "A", "tradeoff": "faster"}]
        with self.assertRaisesRegex(ValueError, "non-empty string"):
            self.publish(state, "Shape the provisional working draft")

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
        state["nodes"][-1] = {**node("recovery-copy", parents=["backup"]),
                              "reopen_reason": "Backup requirement is unresolved"}
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

    def test_reopen_reason_is_validated_and_retained(self):
        before = self.scenario()
        state = self.revised(before)
        state["nodes"][2]["reopen_reason"] = "Import now merges rather than replaces"
        saved = self.publish(state, "New implementation evidence")
        self.assertEqual(saved["nodes"][2]["reopen_reason"], state["nodes"][2]["reopen_reason"])
        self.assertEqual(session.load(self.directory), saved)
        for value in ("", None, 42):
            with self.subTest(value=value):
                state["nodes"][2]["reopen_reason"] = value
                with self.assertRaisesRegex(ValueError, "reopen reason"):
                    self.publish(state)
        self.assertEqual(session.load(self.directory), saved)

    def test_reopened_node_requires_its_own_reason(self):
        before = self.scenario()
        state = self.revised(before)
        state["nodes"][2].pop("reopen_reason")
        with self.assertRaisesRegex(ValueError, "reopened node requires a reopen reason"):
            self.publish(state, "Batch update")
        self.assertEqual(session.load(self.directory), before)

    def test_end_preserves_blockers_and_is_idempotent(self):
        self.scenario()
        state = session.editable(session.load(self.directory))
        state["nodes"].append(node("pending"))
        state["current_question"] = "pending"
        before = self.publish(state)
        with self.assertRaisesRegex(ValueError, "unresolved"):
            session.end(self.directory, "completed", "Not actually complete", no_viewer="not under test")
        self.assertEqual(session.load(self.directory), before)
        ended = session.end(self.directory, "stopped", "User stopped")
        self.assertEqual(ended["status"], "stopped")
        self.assertIsNone(ended["current_question"])
        self.assertEqual(ended["nodes"], before["nodes"])
        self.assertEqual(ended["revision"], before["revision"])
        self.assertEqual(session.end(self.directory, "stopped", "Retry"), ended)
        with self.assertRaisesRegex(ValueError, "read-only"):
            session.end(self.directory, "completed", "Change ended status", no_viewer="not under test")
        with self.assertRaisesRegex(ValueError, "end status"):
            session.end(self.directory, "active", "Resume")

    def test_end_cli_completes_without_changing_answers(self):
        before = self.confirmed()
        result = subprocess.run([sys.executable, str(SCRIPT), "end", str(self.directory),
                                 "--status", "completed", "--reason", "Confirmed pre-intent saved", "--no-viewer", "not under test"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads(result.stdout)
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["nodes"], before["nodes"])
        self.assertEqual(saved["revision"], before["revision"])
        self.assertEqual(session.load(self.directory), saved)

    def test_documented_publication_payloads_run(self):
        reference = (SCRIPT.parents[1] / "references/ledger-transitions.md").read_text()
        section = reference.split("### Publication payload\n", 1)[1].split("### Node Statuses", 1)[0]
        payloads = [json.loads(block) for block in re.findall(r"```json\n(.*?)\n```", section, re.S)]
        self.assertEqual(len(payloads), 2, "Document draft and confirmed-goal publications")
        draft = session.publish(self.directory, **payloads[0])
        self.assertEqual(draft["draft"]["goal"], "Candidate goal")
        self.assertEqual(draft["nodes"], [])
        self.assertIsNone(draft["origin"])
        self.assertEqual(draft["version"], 1)
        saved = session.publish(self.directory, **payloads[1])
        self.assertEqual(saved["version"], 2)
        self.assertEqual(session.load(self.directory), saved)
        nodes = {node["id"]: node for node in saved["nodes"]}
        origin = nodes[saved["origin"]]
        self.assertEqual(origin["kind"], "decision")
        self.assertEqual(origin["status"], "settled")
        self.assertEqual(origin["answer"], saved["goal"])
        self.assertEqual(origin["authority"], "user")
        self.assertTrue(origin["authority_source"])
        self.assertTrue(origin["owner"])
        self.assertTrue(origin["gate"])
        self.assertEqual(origin["evidence"], [])
        facts = [node for node in saved["nodes"] if node["kind"] == "fact"]
        self.assertEqual(len(facts), 1)
        fact = facts[0]
        self.assertEqual(fact["status"], "settled")
        self.assertEqual(fact["authority"], "evidence")
        self.assertTrue(fact["authority_source"])
        self.assertIsInstance(fact["evidence"], list)
        self.assertTrue(fact["evidence"])
        self.assertTrue(all(isinstance(item, str) and item.strip() for item in fact["evidence"]))
        self.assertNotIn("owner", fact)
        self.assertNotIn("gate", fact)

    def test_published_example_is_an_empty_valid_draft(self):
        example = SCRIPT.parents[1] / "assets/ledger.json"
        (self.directory / "ledger.json").write_bytes(example.read_bytes())
        ledger = session.load(self.directory)
        self.assertEqual(ledger["status"], "active")
        self.assertIsNone(ledger["origin"])
        self.assertEqual(ledger["nodes"], [])
        self.assertEqual(ledger["frontier"], [])

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
