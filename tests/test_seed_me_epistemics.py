import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_seed_me_session import node, session


def receipt(**changes):
    return {"checked": "Directory listing of the live skills folder", "at": "2026-10-02T09:15:00+00:00",
            "observed": "4 entries are symlinks into the repository; 2 are plain copies",
            "check": "ls -l ~/.agents/skills", "artifact": "git:7a045e4", **changes}


def finding(node_id, claim, answer, evidence, **extra):
    """A settled fact carrying an explicit epistemic claim."""
    return {"id": node_id, "kind": "fact", "status": "settled", "prerequisites": [], "evidence": evidence,
            "answer": answer, "authority": "evidence", "authority_source": "inspected " + node_id,
            "claim": claim, **extra}


def decision(node_id, parents=("goal",), **extra):
    return {"id": node_id, "kind": "decision", "status": "settled", "prerequisites": list(parents), "evidence": [],
            "owner": "User", "gate": "Choose", "answer": "The repository owns every skill", "authority": "user",
            "authority_source": "chat turn 9: user chose it", **extra}


def acceptance_nodes():
    """The four ledger entries named in the task, split so no entry mixes observation, inference and unknown."""
    return [
        node("goal", answer="Decide how skills are owned and kept safe"),
        finding("layout-observed", {"type": "observation", "scope": "Listing of the live skills folder and repo skills/ on 2026-10-02"},
                "4 live entries are symlinks into the repository; 2 are plain copies.", [receipt()], label="Live vs repository layout"),
        finding("mixed-ownership", {"type": "inference", "scope": "Skill folders in that listing",
                                    "limits": "The layout does not show which side is edited first or which side wins."},
                "The repository appears to own the symlinked skills; the copies may be owned by the live folder.",
                ["Inferred from layout-observed; no document states this"], supported_by=["layout-observed"],
                label="Mixed live and repository ownership"),
        finding("ownership-workflow", {"type": "unknown", "scope": "Only file layout was inspected; no workflow document or user statement was read"},
                "This investigation has not yet established the intended ownership workflow.",
                ["Read README.md and AGENTS.md; neither says which side is edited first"], label="Intended ownership workflow"),
        finding("sdk-version", {"type": "observation", "scope": "Version strings from the runtime and the local SDK manifest",
                                "limits": "Does not show whether the difference affects compatibility."},
                "The runtime reports 2.4.1; the local SDK manifest pins 2.3.0. They differ.",
                [receipt(checked="Runtime and SDK version strings", observed="runtime 2.4.1; sdk 2.3.0", artifact="sdk/package.json sha256:ab12")],
                label="Runtime and local SDK differ"),
        finding("command-paths", {"type": "observation", "scope": "Three handlers read: a.py:12, b.py:40, c.py:77. Other handlers were not read.",
                                  "limits": "Limited handler inspection is not proof that no containment exists anywhere."},
                "Each inspected handler runs commands directly, with no sandbox call in that code.",
                ["a.py:12 subprocess.run(cmd)", "b.py:40 os.system(cmd)", "c.py:77 subprocess.Popen(cmd)"], label="Multiple command execution paths"),
        decision("ownership-policy", label="Skill ownership", supported_by=["mixed-ownership"],
                 rationale={"intent": "One reviewed source of truth for every skill."}),
        {"id": "safety-target", "kind": "decision", "status": "unresolved", "prerequisites": ["goal"], "evidence": [],
         "owner": "User", "gate": "Name what must be protected", "label": "Safety target",
         "question": "What must the command paths be protected against?",
         "recommendation": "Contain command execution in the three inspected handlers first.",
         "rationale": {"feasibility": "Only three handlers are known today, so a wrapper there is the cheapest change."},
         "supported_by": ["command-paths"]},
    ]


class EpistemicCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = session.create(self.temp.name)

    def publish(self, state, reason="Fixture update", **kwargs):
        return session.publish(self.directory, state, session.load(self.directory)["version"], reason, **kwargs)

    def state_with(self, nodes, current=None):
        state = session.editable(session.load(self.directory))
        state.update(goal=nodes[0]["answer"], origin="goal", current_question=current)
        state["nodes"] = copy.deepcopy(nodes)
        return state

    def seed(self, nodes=None, current="safety-target"):
        return self.publish(self.state_with(nodes or acceptance_nodes(), current))

    def edit(self, **by_id):
        state = session.editable(session.load(self.directory))
        for item in state["nodes"]:
            item.update(by_id.get(item["id"], {}))
        return state

    def rejected(self, mutate, pattern):
        state = session.editable(self.seed())
        mutate({n["id"]: n for n in state["nodes"]})
        with self.assertRaisesRegex(ValueError, pattern):
            self.publish(state, "Invalid epistemic state")


class TestFactualSupportVersusDecisionAuthority(EpistemicCase):
    def test_a_fact_is_supported_by_evidence_and_never_authorized_by_a_person(self):
        self.seed()
        for authority in ("user", "delegated", "simulated"):
            with self.subTest(authority=authority):
                self.rejected(lambda n, a=authority: n["mixed-ownership"].update(authority=a), "authority does not match node kind")

    def test_a_decision_cannot_carry_a_finding_type_and_a_fact_cannot_carry_a_rationale(self):
        self.rejected(lambda n: n["ownership-policy"].update(claim={"type": "observation", "scope": "x"}), "claim is only allowed on a fact")
        self.rejected(lambda n: n["sdk-version"].update(rationale={"intent": "x"}), "rationale is only allowed on a decision")

    def test_user_acceptance_does_not_upgrade_the_factual_claims_it_relies_on(self):
        self.seed()
        before = {n["id"]: n for n in session.load(self.directory)["nodes"]}
        state = self.edit(**{"safety-target": {"status": "settled", "answer": "Contain command execution in the three handlers first",
                                                "authority": "user", "authority_source": "chat turn 12: user accepted the proposal"}})
        state["current_question"] = None
        result = self.publish(state, "User accepted the proposal")
        after = {n["id"]: n for n in result["nodes"]}
        for fact_id in ("command-paths", "mixed-ownership", "layout-observed"):
            self.assertEqual(after[fact_id], before[fact_id], "acceptance leaves the findings untouched")
        self.assertEqual((after["command-paths"]["authority"], after["command-paths"]["claim"]["type"]), ("evidence", "observation"))
        self.assertEqual(session.review_flags(result["nodes"]), {}, "accepting a proposal flags nothing and upgrades nothing")

    def test_a_recorded_finding_satisfies_a_prerequisite_without_claiming_it_is_exhaustive(self):
        nodes = acceptance_nodes()
        nodes.append({**node("next-step", parents=["command-paths"]), "question": "What next?"})
        result = self.seed(nodes)
        self.assertIn("next-step", result["frontier"])
        recorded = {n["id"]: n for n in result["nodes"]}["command-paths"]
        self.assertEqual(recorded["claim"]["type"], "observation")
        self.assertIn("not proof", recorded["claim"]["limits"].lower())


class TestUnknownVersusNonexistent(EpistemicCase):
    def test_the_investigation_limit_is_an_unknown_with_a_scope_not_an_absence_claim(self):
        nodes = {n["id"]: n for n in self.seed()["nodes"]}
        unknown = nodes["ownership-workflow"]
        self.assertEqual(unknown["claim"]["type"], "unknown")
        self.assertTrue(unknown["answer"].startswith("This investigation has not yet established"))
        self.assertNotIn("does not exist", unknown["answer"])
        self.assertTrue(unknown["evidence"], "what was read stays recorded")

    def test_an_unknown_must_state_what_was_examined(self):
        self.rejected(lambda n: n["ownership-workflow"].update(claim={"type": "unknown"}), "claim requires a scope")

    def test_an_unknown_can_never_be_cited_as_evidence(self):
        self.rejected(lambda n: n["ownership-policy"].update(supported_by=["ownership-workflow"]), "not a decision or an unknown")
        self.rejected(lambda n: n["mixed-ownership"].update(supported_by=["ownership-workflow"]), "not a decision or an unknown")

    def test_an_unknown_cannot_itself_claim_support(self):
        self.rejected(lambda n: n["ownership-workflow"].update(supported_by=["layout-observed"]), "only allowed on a decision or an inference")

    def test_a_scoped_absence_is_an_observation_with_its_scope_kept(self):
        nodes = acceptance_nodes() + [finding("no-sandbox-seen", {"type": "observation", "scope": "a.py, b.py, c.py only",
                                                                  "limits": "Says nothing about handlers that were not read."},
                                              "No sandbox call appears in a.py, b.py or c.py.", ["grep -n sandbox a.py b.py c.py: no matches"])]
        found = {n["id"]: n for n in self.seed(nodes)["nodes"]}["no-sandbox-seen"]
        self.assertEqual(found["claim"]["scope"], "a.py, b.py, c.py only")


class TestWorkflowVersusEvidence(EpistemicCase):
    def test_supported_by_is_not_a_prerequisite_and_does_not_park_the_node(self):
        nodes = acceptance_nodes()
        nodes[-1]["supported_by"] = ["command-paths"]
        nodes[-1]["prerequisites"] = ["goal"]
        nodes[5].update(status="unresolved", answer=None, authority=None, authority_source=None)
        result = self.seed(nodes)
        flagged = {n["id"]: n for n in result["nodes"]}["safety-target"]
        self.assertEqual(flagged["prerequisites"], ["goal"])
        self.assertIn("safety-target", result["frontier"], "evidence that is not yet recorded does not make the decision wait")

    def test_a_workflow_prerequisite_is_not_evidence_and_never_flags_for_review(self):
        nodes = acceptance_nodes()
        nodes.append({**decision("later-choice", parents=["layout-observed"], answer="Wait for the layout, then choose"),
                      "evidence": ["layout.md:1 the choice follows the layout"]})
        self.seed(nodes)
        state = self.edit(**{"layout-observed": {"answer": "3 live entries are symlinks; 3 are plain copies."}})
        for item in state["nodes"]:
            if item["id"] == "later-choice":
                item["answer"] = "Wait for the layout, then choose"
        with self.assertRaisesRegex(ValueError, "affected settlement requires explicit revalidation.*later-choice"):
            self.publish(state, "Layout changed")
        result = self.publish(state, "Layout changed", revalidated={"later-choice": "Re-read: the choice does not depend on the count",
                                                                    "ownership-policy": "Reviewed with the layout change"})
        self.assertNotIn("later-choice", session.review_flags(result["nodes"]), "workflow order is not evidential support")

    def test_support_must_name_real_non_self_distinct_findings(self):
        for label, value, pattern in (("self", ["ownership-policy"], "another node"), ("missing", ["nope"], "another node"),
                                      ("duplicate", ["mixed-ownership", "mixed-ownership"], "invalid supported_by"),
                                      ("empty", [], "invalid supported_by"), ("not a list", "mixed-ownership", "invalid supported_by"),
                                      ("a decision", ["goal"], "not a decision or an unknown")):
            with self.subTest(label):
                self.rejected(lambda n, v=value: n["ownership-policy"].update(supported_by=v), pattern)

    def test_an_inference_is_supported_by_observations_not_other_inferences_or_legacy_notes(self):
        nodes = acceptance_nodes()
        nodes.append(finding("more-ownership", {"type": "inference", "scope": "s", "limits": "l"}, "Another conclusion", ["note"], supported_by=["mixed-ownership"]))
        with self.assertRaisesRegex(ValueError, "supported by observations"):
            self.seed(nodes)
        nodes = acceptance_nodes()
        nodes.append({**finding("legacy", {"type": "observation", "scope": "s"}, "A fact", ["note"]), "id": "legacy"})
        del nodes[-1]["claim"]
        nodes.append(finding("from-legacy", {"type": "inference", "scope": "s", "limits": "l"}, "Concluded", ["note"], supported_by=["legacy"]))
        with self.assertRaisesRegex(ValueError, "supported by observations"):
            self.seed(nodes)


class TestEvidenceChangesFlagReviewWithoutRewritingDecisions(EpistemicCase):
    def change_observation(self):
        state = self.edit(**{"layout-observed": {"answer": "3 live entries are symlinks; 3 are plain copies.",
                                                 "evidence": [receipt(at="2026-10-03T08:00:00+00:00", observed="3 symlinks; 3 copies")]}})
        return self.publish(state, "Re-listed the folders; the counts changed")

    def test_changed_evidence_flags_the_claim_and_the_decision_without_touching_the_decision(self):
        self.seed()
        before = {n["id"]: n for n in session.load(self.directory)["nodes"]}["ownership-policy"]
        result = self.change_observation()
        after = {n["id"]: n for n in result["nodes"]}["ownership-policy"]
        flags = session.review_flags(result["nodes"])
        self.assertEqual(flags["mixed-ownership"], [{"because": "layout-observed", "why": "changed"}])
        self.assertEqual(flags["ownership-policy"], [{"because": "mixed-ownership", "why": "under review"}])
        for field in ("status", "answer", "authority", "authority_source", "supported_by", "rationale", "revision", "history"):
            self.assertEqual(after[field], before[field], field + " is untouched by a review flag")
        self.assertIsNone(after.get("reopen_reason"))
        self.assertNotIn("replacement", json.dumps(after))

    def test_withdrawn_and_contradicted_evidence_flag_too(self):
        self.seed()
        state = self.edit(**{"layout-observed": {"status": "unresolved", "answer": None, "authority": None, "authority_source": None,
                                                 "reopen_reason": "The listing was of the wrong folder"}})
        result = self.publish(state, "Withdraw the observation")  # evidence is not a prerequisite, so the inference is flagged rather than forced open
        flags = session.review_flags(result["nodes"])
        self.assertEqual(flags["mixed-ownership"], [{"because": "layout-observed", "why": "withdrawn"}])
        self.assertEqual({n["id"]: n for n in result["nodes"]}["mixed-ownership"]["status"], "settled")
        state = self.edit(**{"layout-observed": {"status": "superseded", "reopen_reason": None}})
        state["nodes"][1].pop("reopen_reason")
        result = self.publish(state, "Superseded: the listing was of the wrong folder")
        self.assertEqual(session.review_flags(result["nodes"])["mixed-ownership"], [{"because": "layout-observed", "why": "withdrawn"}])

    def test_a_contradicting_fact_flags_what_relied_on_the_contradicted_claim(self):
        self.seed()
        nodes = acceptance_nodes() + [finding("listing-was-stale", {"type": "observation", "scope": "A second listing"}, "The first listing was stale.",
                                              ["ls -l again"], contradicts="layout-observed")]
        state = self.state_with(nodes, "safety-target")
        result = self.publish(state, "A later check contradicts the first listing")
        self.assertEqual(session.review_flags(result["nodes"])["mixed-ownership"], [{"because": "layout-observed", "why": "contradicted"}])

    def test_unreviewed_flags_block_completion_and_review_clears_them_without_changing_answers(self):
        self.seed()
        state = self.edit(**{"safety-target": {"status": "deferred", "defer_reason": "later", "revisit_condition": "after review"}})
        state["current_question"] = None
        self.publish(state, "Defer the open choice")
        self.change_observation()
        with self.assertRaisesRegex(ValueError, "cannot complete: evidence behind these settled nodes.*mixed-ownership.*ownership-policy"):
            session.end(self.directory, "completed", "Done", no_viewer="not under test")
        with self.assertRaisesRegex(ValueError, "invalid revalidation targets"):
            self.publish(session.editable(session.load(self.directory)), "Not flagged", revalidated={"sdk-version": "Nothing changed here"})
        with self.assertRaisesRegex(ValueError, "justification"):
            self.publish(session.editable(session.load(self.directory)), "Blank", revalidated={"mixed-ownership": " "})
        answer = {n["id"]: n for n in session.load(self.directory)["nodes"]}["ownership-policy"]["answer"]
        result = self.publish(session.editable(session.load(self.directory)), "User re-read the new listing and kept the choice",
                              revalidated={"mixed-ownership": "Counts changed; the inference still holds", "ownership-policy": "User kept the decision after review"})
        policy = {n["id"]: n for n in result["nodes"]}["ownership-policy"]
        self.assertEqual((policy["answer"], policy["authority"]), (answer, "user"))
        self.assertEqual(session.review_flags(result["nodes"]), {})
        self.assertEqual(policy["history"][-1]["reason"], "User kept the decision after review")
        self.assertEqual(session.end(self.directory, "completed", "Done", no_viewer="not under test")["status"], "completed")

    def test_review_flags_are_derived_not_stored(self):
        result = self.seed()
        self.change_observation()
        stored = session.load(self.directory)
        stored_keys = set(stored) | {k for n in stored["nodes"] for k in n}
        self.assertFalse(stored_keys & {"review", "review_flags", "needs_review", "flags"}, "only the helper-owned counters are stored, never the flags")
        self.assertTrue({"premise_version", "reviewed_version"} <= {k for n in stored["nodes"] for k in n})
        self.assertTrue(session.review_flags(stored["nodes"]))

class TestReviewFlagsOnlyClearByExplicitReview(EpistemicCase):
    """A flag is cleared by revalidating the flagged node, never by an unrelated edit."""

    FLAGGED = ["contain-handlers", "mixed-ownership", "ownership-policy"]

    def changed(self):
        """contain-handlers relies directly on command-paths; the other two rely on layout-observed (one through the inference)."""
        self.seed(acceptance_nodes() + [decision("contain-handlers", answer="Wrap the three handlers", supported_by=["command-paths"])])
        state = self.edit(**{"layout-observed": {"answer": "3 live entries are symlinks; 3 are plain copies."},
                             "command-paths": {"answer": "Each inspected handler runs commands directly; one has a timeout."}})
        return self.publish(state, "Re-checked both; the findings changed")

    def assert_still_flagged(self, result):
        self.assertEqual(sorted(session.review_flags(result["nodes"])), self.FLAGGED)
        with self.assertRaisesRegex(ValueError, "cannot complete: evidence behind these settled nodes"):
            self.complete()

    def complete(self):
        state = self.edit(**{"safety-target": {"status": "deferred", "defer_reason": "later", "revisit_condition": "after review"}})
        state["current_question"] = None
        try:
            self.publish(state, "Defer the open choice")
        except ValueError:
            pass
        return session.end(self.directory, "completed", "Done", no_viewer="not under test")

    def test_editing_the_dependents_label_does_not_clear_the_flag(self):
        self.changed()
        result = self.publish(self.edit(**{"contain-handlers": {"label": "Renamed", "question": "Wrap which handlers?"}}), "Rename the decision")
        self.assert_still_flagged(result)

    def test_editing_the_inferences_or_decisions_other_fields_does_not_clear_the_flag(self):
        self.changed()
        result = self.publish(self.edit(**{"mixed-ownership": {"label": "Renamed"}, "contain-handlers": {"owner": "Someone else", "gate": "Other gate"},
                                           "ownership-policy": {"label": "Also renamed"}}), "Edit unrelated fields")
        self.assert_still_flagged(result)

    def test_editing_the_decisions_answer_without_review_does_not_clear_the_flag(self):
        self.changed()
        result = self.publish(self.edit(**{"contain-handlers": {"answer": "Wrap every handler"}}), "Change the answer, no review")
        self.assert_still_flagged(result)

    def test_a_label_edit_on_the_evidence_does_not_flag_what_relies_on_it(self):
        self.seed(acceptance_nodes() + [decision("contain-handlers", answer="Wrap the three handlers", supported_by=["command-paths"])])
        result = self.publish(self.edit(**{"layout-observed": {"label": "Renamed observation"}, "command-paths": {"label": "Renamed too"}}), "Rename only")
        self.assertEqual(session.review_flags(result["nodes"]), {})

    def test_explicit_revalidation_still_clears_the_flag(self):
        self.changed()
        self.publish(self.edit(**{"contain-handlers": {"label": "Renamed"}}), "Rename the decision")
        result = self.publish(session.editable(session.load(self.directory)), "Reviewed with the user",
                              revalidated={"mixed-ownership": "Counts changed; still holds", "ownership-policy": "User kept the decision",
                                           "contain-handlers": "User kept the decision"})
        self.assertEqual(session.review_flags(result["nodes"]), {})

    def test_evidence_that_changes_again_after_a_review_flags_again(self):
        self.changed()
        self.publish(session.editable(session.load(self.directory)), "Reviewed",
                     revalidated={"mixed-ownership": "Still holds", "ownership-policy": "Kept", "contain-handlers": "Kept"})
        result = self.publish(self.edit(**{"command-paths": {"answer": "Each inspected handler runs commands directly; two have timeouts."}}), "Changed again")
        self.assertEqual(sorted(session.review_flags(result["nodes"])), ["contain-handlers"])

    def test_the_helper_owned_counters_are_not_accepted_in_a_publication(self):
        state = session.editable(self.seed())
        state["nodes"][1]["reviewed_version"] = 99
        with self.assertRaisesRegex(ValueError, "invalid node fields"):
            self.publish(state, "Forge a review")


class TestEveryFlaggedNodeNeedsItsOwnReview(EpistemicCase):
    """Observation -> inference -> decision: each flagged node is cleared by its own explicit review, and review can always be given."""

    def seeded(self):
        self.seed()
        state = self.edit(**{"layout-observed": {"answer": "3 live entries are symlinks; 3 are plain copies."}})
        return self.publish(state, "Re-listed the folders; the counts changed")

    def finish(self):
        state = self.edit(**{"safety-target": {"status": "deferred", "defer_reason": "later", "revisit_condition": "after review"}})
        state["current_question"] = None
        try:
            self.publish(state, "Defer the open choice")
        except ValueError:
            pass
        return session.end(self.directory, "completed", "Done", no_viewer="not under test")

    def review(self, **reasons):
        return self.publish(session.editable(session.load(self.directory)), "Review", revalidated=reasons)

    def test_reviewing_only_the_inference_leaves_the_decision_flagged_and_completion_blocked(self):
        result = self.seeded()
        self.assertEqual(sorted(session.review_flags(result["nodes"])), ["mixed-ownership", "ownership-policy"])
        result = self.review(**{"mixed-ownership": "Counts changed; the inference still holds"})
        flags = session.review_flags(result["nodes"])
        self.assertEqual(sorted(flags), ["ownership-policy"], "the inference is reviewed; the decision is not")
        self.assertEqual(flags["ownership-policy"], [{"because": "mixed-ownership", "why": "changed"}])
        with self.assertRaisesRegex(ValueError, "cannot complete: evidence behind these settled nodes.*ownership-policy"):
            self.finish()
        policy = {n["id"]: n for n in result["nodes"]}["ownership-policy"]
        self.assertEqual((policy["answer"], policy["authority"]), ("The repository owns every skill", "user"))

    def test_the_decision_clears_when_it_is_reviewed_in_its_own_right(self):
        self.seeded()
        self.review(**{"mixed-ownership": "Still holds"})
        result = self.review(**{"ownership-policy": "User saw the changed evidence and kept the decision"})
        self.assertEqual(session.review_flags(result["nodes"]), {})
        self.assertEqual(self.finish()["status"], "completed")

    def test_reviewing_the_inference_and_the_decision_together_clears_both(self):
        self.seeded()
        result = self.review(**{"mixed-ownership": "Still holds", "ownership-policy": "User kept the decision"})
        self.assertEqual(session.review_flags(result["nodes"]), {})

    def test_withdrawn_evidence_can_be_acknowledged_by_reviewing_the_decision(self):
        self.seed(acceptance_nodes() + [decision("contain-handlers", answer="Wrap the three handlers", supported_by=["command-paths"])])
        state = self.edit(**{"command-paths": {"status": "superseded", "answer": None, "authority": None, "authority_source": None}})
        result = self.publish(state, "The handler read was of the wrong folder")
        self.assertEqual(session.review_flags(result["nodes"])["contain-handlers"], [{"because": "command-paths", "why": "withdrawn"}])
        result = self.review(**{"contain-handlers": "User confirmed the choice without that evidence"})
        self.assertNotIn("contain-handlers", session.review_flags(result["nodes"]))
        self.assertEqual({n["id"]: n for n in result["nodes"]}["command-paths"]["status"], "superseded", "the evidence stays withdrawn")
        self.assertEqual(self.finish()["status"], "completed")

    def test_evidence_that_returns_after_a_withdrawal_must_be_reviewed_again(self):
        self.seed(acceptance_nodes() + [decision("contain-handlers", answer="Wrap the three handlers", supported_by=["command-paths"])])
        state = self.edit(**{"command-paths": {"status": "unresolved", "answer": None, "authority": None, "authority_source": None,
                                               "reopen_reason": "Re-reading the handlers"}})
        self.publish(state, "Withdraw while re-reading")
        self.review(**{"contain-handlers": "Confirmed without it"})
        state = self.edit(**{"command-paths": {"status": "settled", "answer": "Each inspected handler runs commands directly.", "authority": "evidence",
                                               "authority_source": "re-read a.py b.py c.py"}})
        state["nodes"] = [{k: v for k, v in n.items() if k != "reopen_reason"} for n in state["nodes"]]
        result = self.publish(state, "Re-recorded the finding")
        self.assertEqual(session.review_flags(result["nodes"])["contain-handlers"], [{"because": "command-paths", "why": "changed"}])

    def test_a_node_settled_on_unsettled_evidence_starts_out_flagged(self):
        nodes = acceptance_nodes() + [decision("contain-handlers", answer="Wrap the three handlers", supported_by=["pending-fact"]),
                                      {**node("pending-fact", "fact"), "claim": {"type": "observation", "scope": "not read yet"}}]
        result = self.seed(nodes)
        self.assertEqual(session.review_flags(result["nodes"])["contain-handlers"], [{"because": "pending-fact", "why": "withdrawn"}])

    def test_a_contradiction_is_acknowledged_by_reviewing_what_relied_on_the_contradicted_claim(self):
        self.seed()
        nodes = acceptance_nodes() + [finding("listing-was-stale", {"type": "observation", "scope": "A second listing"}, "The first listing was stale.",
                                              ["ls -l again"], contradicts="layout-observed")]
        result = self.publish(self.state_with(nodes, "safety-target"), "A later check contradicts the first listing")
        self.assertEqual(session.review_flags(result["nodes"])["mixed-ownership"], [{"because": "layout-observed", "why": "contradicted"}])
        result = self.review(**{"mixed-ownership": "Reviewed against the second listing", "ownership-policy": "User kept the decision"})
        self.assertEqual(session.review_flags(result["nodes"]), {})


class TestLegacyDataAndHistory(EpistemicCase):
    def legacy(self):
        nodes = [node("goal", answer="Recover data"), node("import-behavior", "fact", answer="Imports replace existing data"),
                 node("backup", parents=["import-behavior"], answer="Require backup before import")]
        return self.publish(self.state_with(nodes, None), "Legacy publication, before findings were typed")

    def test_legacy_ledgers_load_unchanged_and_nothing_is_rewritten_by_reading(self):
        self.legacy()
        path = Path(self.directory) / "ledger.json"
        before = path.read_bytes()
        loaded = session.load(self.directory)
        self.assertEqual(path.read_bytes(), before)
        fact = {n["id"]: n for n in loaded["nodes"]}["import-behavior"]
        self.assertNotIn("claim", fact)
        self.assertIsInstance(fact["evidence"][0], str, "legacy string evidence is not turned into an invented receipt")
        self.assertEqual(session.review_flags(loaded["nodes"]), {})
        self.assertEqual(loaded["schema_version"], 1)

    def test_classifying_a_legacy_entry_keeps_ids_answers_authority_and_history(self):
        loaded = self.legacy()
        before = {n["id"]: n for n in loaded["nodes"]}
        state = self.edit(**{"import-behavior": {"claim": {"type": "observation", "scope": "import.py:10 only"}}})
        result = self.publish(state, "Classified the legacy fact after re-reading import.py")
        after = {n["id"]: n for n in result["nodes"]}
        self.assertEqual(list(after), list(before))
        for node_id, old in before.items():
            for field in ("answer", "authority", "authority_source", "evidence", "status"):
                self.assertEqual(after[node_id].get(field), old.get(field), (node_id, field))
        self.assertEqual(result["revision"], loaded["revision"], "labeling a legacy entry changes no premise")
        self.assertEqual(after["backup"]["revision"], before["backup"]["revision"])
        self.assertEqual(after["backup"]["status"], "settled", "dependents of a classified entry stay settled")
        history = after["import-behavior"]["history"]
        self.assertEqual(len(history), 1)
        self.assertNotIn("claim", history[0]["state"])
        self.assertEqual(history[0]["reason"], "Classified the legacy fact after re-reading import.py")

    def test_a_legacy_entry_can_stay_unclassified_and_is_never_guessed(self):
        self.legacy()
        for item in session.load(self.directory)["nodes"]:
            if item["kind"] == "fact":
                self.assertNotIn("claim", item)

    def test_reclassifying_a_settled_finding_is_a_premise_change_that_reaches_dependents(self):
        self.seed()
        state = self.edit(**{"layout-observed": {"claim": {"type": "observation", "scope": "A narrower listing"}}})
        result = self.publish(state, "The listing covered less than first recorded")
        self.assertEqual(session.review_flags(result["nodes"])["mixed-ownership"], [{"because": "layout-observed", "why": "changed"}])

    def test_an_old_helper_style_ledger_without_new_fields_still_publishes_and_completes(self):
        self.legacy()
        state = session.editable(session.load(self.directory))
        self.publish(state, "No-op republish")
        self.assertEqual(session.end(self.directory, "completed", "Done", no_viewer="not under test")["status"], "completed")


class TestAcceptanceExamples(EpistemicCase):
    def test_mixed_ownership_separates_the_observed_layout_the_inference_and_the_unknown(self):
        nodes = {n["id"]: n for n in self.seed()["nodes"]}
        self.assertEqual(nodes["layout-observed"]["claim"]["type"], "observation")
        inferred = nodes["mixed-ownership"]
        self.assertEqual((inferred["claim"]["type"], inferred["supported_by"]), ("inference", ["layout-observed"]))
        self.assertIn("does not show", inferred["claim"]["limits"])
        self.assertEqual(nodes["ownership-workflow"]["answer"], "This investigation has not yet established the intended ownership workflow.")
        self.assertNotIn("mixed-ownership", nodes["layout-observed"].get("supported_by", []))

    def test_runtime_and_sdk_differ_records_the_difference_without_a_compatibility_claim(self):
        found = {n["id"]: n for n in self.seed()["nodes"]}["sdk-version"]
        self.assertEqual(found["claim"]["type"], "observation")
        self.assertNotIn("incompatib", found["answer"].lower())
        self.assertIn("does not show whether", found["claim"]["limits"].lower())

    def test_command_paths_keep_their_scope_and_never_assert_global_absence(self):
        found = {n["id"]: n for n in self.seed()["nodes"]}["command-paths"]
        self.assertIn("Other handlers were not read", found["claim"]["scope"])
        self.assertIn("not proof that no containment exists anywhere", found["claim"]["limits"])

    def test_safety_target_stays_a_provisional_proposal_resting_on_feasibility_alone(self):
        result = self.seed()
        target = {n["id"]: n for n in result["nodes"]}["safety-target"]
        self.assertEqual((target["status"], target.get("answer"), target.get("authority"), target.get("authority_source")), ("unresolved", None, None, None))
        self.assertIn("feasibility", target["rationale"])
        self.assertNotIn("intent", target["rationale"])
        self.assertEqual(result["current_question"], "safety-target")


class TestRecommendationsStayProposals(EpistemicCase):
    def test_a_recommendation_alone_never_becomes_an_answer_or_an_authority(self):
        target = {n["id"]: n for n in self.seed()["nodes"]}["safety-target"]
        self.assertTrue(target["recommendation"])
        self.assertIsNone(target.get("answer"))
        self.assertIsNone(target.get("authority"))

    def test_settling_without_a_recorded_user_choice_is_rejected(self):
        self.rejected(lambda n: n["safety-target"].update(status="settled", answer=n["safety-target"]["recommendation"]), "authority source")
        self.rejected(lambda n: n["safety-target"].update(status="settled", answer="x", authority_source="agent recommendation", authority="agent"),
                      "authority does not match")

    def test_changing_a_recommendation_never_edits_a_recorded_answer(self):
        self.seed()
        state = self.edit(**{"ownership-policy": {"recommendation": "A different proposal"}})
        result = self.publish(state, "Agent revised its proposal")
        policy = {n["id"]: n for n in result["nodes"]}["ownership-policy"]
        self.assertEqual((policy["answer"], policy["authority"]), ("The repository owns every skill", "user"))

    def test_authorization_provenance_stays_separate_from_factual_provenance(self):
        policy = {n["id"]: n for n in self.seed()["nodes"]}["ownership-policy"]
        self.assertEqual(policy["evidence"], [])
        self.assertEqual(policy["supported_by"], ["mixed-ownership"])
        self.assertTrue(policy["authority_source"].startswith("chat turn"))

    def test_rationale_keeps_feasibility_apart_from_the_users_outcome(self):
        nodes = {n["id"]: n for n in self.seed()["nodes"]}
        self.assertEqual(set(nodes["safety-target"]["rationale"]), {"feasibility"})
        self.assertEqual(set(nodes["ownership-policy"]["rationale"]), {"intent"})
        self.rejected(lambda n: n["safety-target"].update(rationale={}), "invalid rationale")
        self.rejected(lambda n: n["safety-target"].update(rationale={"because": "x"}), "invalid rationale")
        self.rejected(lambda n: n["safety-target"].update(rationale={"intent": " "}), "invalid rationale")


class TestInvalidEpistemicStatesAreRejected(EpistemicCase):
    def test_invalid_claims(self):
        cases = (
            ("unknown type", lambda n: n["sdk-version"].update(claim={"type": "verified", "scope": "x"}), "invalid claim"),
            ("null claim", lambda n: n["sdk-version"].update(claim=None), "invalid claim"),
            ("extra claim key", lambda n: n["sdk-version"].update(claim={"type": "observation", "scope": "x", "confidence": 0.9}), "invalid claim"),
            ("no scope", lambda n: n["sdk-version"].update(claim={"type": "observation"}), "requires a scope"),
            ("blank scope", lambda n: n["sdk-version"].update(claim={"type": "observation", "scope": " "}), "requires a scope"),
            ("blank limits", lambda n: n["sdk-version"].update(claim={"type": "observation", "scope": "x", "limits": ""}), "invalid claim limits"),
            ("inference without limits", lambda n: n["mixed-ownership"].update(claim={"type": "inference", "scope": "x"}), "must state its limits"),
            ("inference without support", lambda n: n["mixed-ownership"].pop("supported_by"), "must cite the observations"),
            ("observation with support", lambda n: n["sdk-version"].update(supported_by=["command-paths"]), "only allowed on a decision or an inference"),
            ("support from a decision", lambda n: n["ownership-policy"].update(supported_by=["safety-target"]), "not a decision or an unknown"),
        )
        for label, mutate, pattern in cases:
            with self.subTest(label):
                self.rejected(mutate, pattern)

    def test_numeric_confidence_is_not_part_of_the_model(self):
        self.rejected(lambda n: n["mixed-ownership"].update(confidence=0.8), "invalid node fields")

    def test_invalid_receipts(self):
        cases = (
            ("missing observed", {k: v for k, v in receipt().items() if k != "observed"}, "invalid receipt"),
            ("missing checked", {k: v for k, v in receipt().items() if k != "checked"}, "invalid receipt"),
            ("extra key", receipt(note="x"), "invalid receipt"),
            ("blank artifact", receipt(artifact=" "), "invalid receipt"),
            ("not a time", receipt(at="yesterday"), "invalid receipt time"),
            ("time without a zone", receipt(at="2026-10-02T09:15:00"), "invalid receipt time"),
            ("secret in the check", receipt(check="curl -H 'Authorization: Bearer abcdef0123456789abcdef' https://x"), "contain a secret"),
            ("secret in observed", receipt(observed="found AKIAABCDEFGHIJKLMNOP in the file"), "contain a secret"),
            ("key block", receipt(observed="-----BEGIN RSA PRIVATE KEY-----"), "contain a secret"),
            ("assignment", receipt(check="export API_KEY=supersecretvalue"), "contain a secret"),
            ("url credentials", receipt(check="git clone https://user:hunter2@example.com/r.git"), "contain a secret"),
        )
        for label, bad, pattern in cases:
            with self.subTest(label):
                self.rejected(lambda n, b=bad: n["layout-observed"].update(evidence=[b]), pattern)

    def test_non_string_non_receipt_evidence_is_rejected(self):
        for bad in (5, None, ["nested"], " "):
            with self.subTest(bad=bad):
                self.rejected(lambda n, b=bad: n["layout-observed"].update(evidence=[b]), "invalid evidence|invalid receipt")


class TestReceipts(EpistemicCase):
    def test_receipts_and_legacy_strings_coexist_and_round_trip_exactly(self):
        mixed = [receipt(), "legacy note: import.py:10"]
        nodes = acceptance_nodes()
        nodes[1]["evidence"] = copy.deepcopy(mixed)
        result = self.seed(nodes)
        self.assertEqual({n["id"]: n for n in result["nodes"]}["layout-observed"]["evidence"], mixed)
        self.assertEqual({n["id"]: n for n in session.load(self.directory)["nodes"]}["layout-observed"]["evidence"], mixed)

    def test_a_stored_check_is_data_and_is_never_executed(self):
        marker = Path(self.temp.name) / "executed"
        nodes = acceptance_nodes()
        nodes[1]["evidence"] = [receipt(check=f"touch {marker}")]
        self.seed(nodes)
        session.load(self.directory)
        self.assertFalse(marker.exists())

    def test_optional_check_and_artifact_may_be_omitted_and_are_not_invented(self):
        nodes = acceptance_nodes()
        bare = {"checked": "README.md", "at": "2026-10-02T09:15:00Z", "observed": "No ownership workflow is described"}
        nodes[1]["evidence"] = [bare]
        found = {n["id"]: n for n in self.seed(nodes)["nodes"]}["layout-observed"]
        self.assertEqual(found["evidence"], [bare])

    def test_settling_a_fact_still_requires_some_evidence(self):
        self.rejected(lambda n: n["layout-observed"].update(evidence=[]), "requires evidence")

    def test_a_changed_receipt_artifact_counts_as_changed_evidence_for_what_relies_on_it(self):
        nodes = acceptance_nodes() + [decision("contain-handlers", answer="Wrap the three handlers", supported_by=["command-paths"])]
        self.seed(nodes)
        state = self.edit(**{"command-paths": {"evidence": [receipt(artifact="git:newer")] + ["a.py:12 subprocess.run(cmd)"]}})
        result = self.publish(state, "Re-checked at a newer commit")
        self.assertEqual(session.review_flags(result["nodes"])["contain-handlers"], [{"because": "command-paths", "why": "changed"}])
        decided = {n["id"]: n for n in result["nodes"]}["contain-handlers"]
        self.assertEqual((decided["answer"], decided["authority"]), ("Wrap the three handlers", "user"))

if __name__ == "__main__":
    unittest.main()
