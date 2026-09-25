"""Exercise fit decisions through durable receipts and final ranking eligibility."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

SCRIPT = Path(__file__).resolve().parents[1] / "skills/skill-scout/scripts/jev_fit.py"
spec = importlib.util.spec_from_file_location("jev_fit", SCRIPT)
jev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev)


def packet():
    return {
        "schema_version": 1,
        "contract": {"transformation": "Turn incident evidence into a cited brief",
                     "inputs": ["incident evidence"], "outputs": ["cited brief"],
                     "constraints": ["read-only"], "acceptable_adaptation": "one template change"},
        "candidate": {"id": "brief", "source_class": "public_repository",
                      "source": "https://github.com/example/brief", "skill_path": "skills/brief",
                      "revision": "a" * 40, "snapshot_sha256": None},
        "evidence": [{"id": "e1", "source": "SKILL.md:10-15", "kind": "implementation",
                      "basis": "observed", "text": "Each brief statement includes its input source ID."}],
        "proposed_adaptation": None,
        "unknowns": [], "coverage": {"inspected": "brief implementation", "omissions": []},
    }


def policy():
    # A fixture threshold, not a recommended or calibrated production value.
    return {"version": "test-only", "model": "jev-1.13.0", "confidence_threshold": .8,
            "max_input_bytes": 24000}


def response(choice="exact_fit", confidence=.99):
    return {"model": "jev-1.13.0", "answers": {"fit": {"type": "choice", "choice": choice,
            "probabilities": {k: float(k == choice) for k in jev.CRITERIA},
            "confidence": confidence}}, "usage": {"input_tokens": 100, "output_tokens": 20}}


class JevFitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.packet, self.policy = packet(), policy()
        self.gates = dict.fromkeys(jev.OTHER_GATES, "pass")

    def decide(self, value, packet_value=None, **kwargs):
        p = packet_value or self.packet
        return jev.decide(p, self.policy, self.root, jev.digest(p), call=Mock(return_value=value), **kwargs)

    def qualify(self, p=None):
        return jev.qualify(p or self.packet, self.policy, self.root, self.gates)

    def test_each_outcome_changes_final_eligibility(self):
        for choice, expected in [("exact_fit", True), ("fits_with_named_adaptation", True),
                                 ("wrong_transformation", False), ("insufficient_evidence", False)]:
            with self.subTest(choice=choice), tempfile.TemporaryDirectory() as directory:
                p = packet()
                p["proposed_adaptation"] = {"change": "rename template headings", "affected_requirements": ["cited brief"],
                                            "evidence_ids": ["e1"], "within_scope_because": "one template change"}
                result = jev.decide(p, self.policy, directory, jev.digest(p), call=Mock(return_value=response(choice)))
                final = jev.qualify(p, self.policy, directory, self.gates)
                self.assertEqual(final["eligible_for_ranking"], expected)
                self.assertEqual(result["response"]["answers"]["fit"]["choice"], choice)
                self.assertEqual(final["gate_statuses"]["workflow_fit"], result["fit_status"])
                self.assertEqual(final["adaptation"] is not None, choice == "fits_with_named_adaptation")

    def test_other_gate_failure_or_unknown_blocks_exact_fit(self):
        self.decide(response())
        for gate in jev.OTHER_GATES:
            for status in ("fail", "unresolved"):
                self.gates = dict.fromkeys(jev.OTHER_GATES, "pass")
                self.gates[gate] = status
                self.assertFalse(self.qualify()["eligible_for_ranking"])

    def test_low_confidence_retains_choice_but_prevents_ranking(self):
        result = self.decide(response(confidence=.64))
        self.assertEqual(result["response"]["answers"]["fit"]["choice"], "exact_fit")
        self.assertEqual(result["disposition"], "low_confidence")
        self.assertFalse(self.qualify()["eligible_for_ranking"])

    def test_invalid_provider_responses_are_retained_but_unresolved(self):
        mutations = [
            lambda r: r.update(model="jev-latest"),
            lambda r: r["answers"]["fit"].update(choice="invented"),
            lambda r: r["answers"]["fit"].update(choice=["exact_fit"]),
            lambda r: r["answers"]["fit"].update(confidence=float("nan")),
            lambda r: r["answers"]["fit"].update(confidence=True),
            lambda r: r["answers"]["fit"].update(probabilities={"exact_fit": 1}),
            lambda r: r["answers"]["fit"]["probabilities"].update(exact_fit=-1),
            lambda r: r["answers"]["fit"]["probabilities"].update(exact_fit=.4),
            lambda r: r["answers"]["fit"].update(type="score"),
            lambda r: r["answers"]["fit"].update(choice="wrong_transformation"),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                p = packet()
                p["candidate"]["id"] = f"candidate-{index}"
                r = response()
                mutate(r)
                receipt = self.decide(r, p)
                self.assertIsNotNone(receipt["error"])
                self.assertIsNotNone(receipt["response"])
                self.assertFalse(self.qualify(p)["eligible_for_ranking"])

    def test_adaptation_and_empty_evidence_cannot_receive_pass(self):
        result = self.decide(response("fits_with_named_adaptation"))
        self.assertEqual(result["error"], "missing_adaptation")
        p = packet()
        p["candidate"]["id"] = "empty"
        p["evidence"] = []
        result = self.decide(response(), p)
        self.assertEqual(result["error"], "missing_fit_evidence")
        self.assertFalse(self.qualify(p)["eligible_for_ranking"])

    def test_unauthorized_or_changed_packet_never_calls_provider(self):
        call = Mock()
        for authorization in (None, "yes", "sha256:" + "0" * 64):
            with self.assertRaisesRegex(jev.Invalid, "payload_not_authorized"):
                jev.decide(self.packet, self.policy, self.root, authorization, call=call)
        authorization = jev.digest(self.packet)
        self.packet["unknowns"].append("new information")
        with self.assertRaisesRegex(jev.Invalid, "payload_not_authorized"):
            jev.decide(self.packet, self.policy, self.root, authorization, call=call)
        call.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_bad_packet_policy_and_input_limit_fail_preflight(self):
        mutations = [
            lambda p: p["candidate"].update(id="../escape"),
            lambda p: p["candidate"].update(revision="main"),
            lambda p: p["candidate"].update(revision=None),
            lambda p: p.update(authorization="approved"),
            lambda p: p["evidence"].append(copy.deepcopy(p["evidence"][0])),
            lambda p: p.update(proposed_adaptation={"change": "rename", "affected_requirements": ["brief"],
                                                   "evidence_ids": ["missing"], "within_scope_because": "small"}),
        ]
        for mutate in mutations:
            p = packet()
            mutate(p)
            with self.assertRaises(jev.Invalid):
                jev.preflight(p, self.policy)
        for threshold in (None, True, float("nan"), -.1, 1.1, 10**1000):
            self.policy["confidence_threshold"] = threshold
            with self.assertRaises(jev.Invalid):
                jev.preflight(self.packet, self.policy)
        self.policy = policy()
        self.policy["max_input_bytes"] = 10
        with self.assertRaisesRegex(jev.Invalid, "input_limit"):
            jev.preflight(self.packet, self.policy)

    def test_known_key_in_payload_is_rejected_without_echo(self):
        with patch.dict(os.environ, {"TYPESAFE_API_KEY": "private-test-key"}):
            self.packet["evidence"][0]["text"] = "private-test-key"
            with self.assertRaisesRegex(jev.Invalid, "credential_in_payload"):
                jev.preflight(self.packet, self.policy)

    def test_replay_budget_and_policy_drift(self):
        call = Mock(return_value=response())
        jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
        with self.assertRaisesRegex(jev.Invalid, "packet_already_attempted"):
            jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
        self.packet["unknowns"].append("new source inspected")
        jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
        self.packet["unknowns"].append("third attempt")
        with self.assertRaisesRegex(jev.Invalid, "revision_budget_exhausted"):
            jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
        self.assertEqual(call.call_count, 2)
        self.policy["confidence_threshold"] = .5
        self.packet["candidate"]["id"] = "another"
        with self.assertRaisesRegex(jev.Invalid, "run_policy_drift"):
            jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)

    def test_pending_crash_cannot_be_replayed_or_recommended(self):
        call = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
        self.assertFalse(self.qualify()["eligible_for_ranking"])
        with self.assertRaisesRegex(jev.Invalid, "attempt_incomplete"):
            jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
        call.assert_called_once()

    def test_provider_error_does_not_expose_message_or_retry(self):
        for index, error in enumerate([TimeoutError("secret"), RuntimeError("secret")]):
            p = packet()
            p["candidate"]["id"] = f"failed-{index}"
            call = Mock(side_effect=error)
            receipt = jev.decide(p, self.policy, self.root, jev.digest(p), call=call)
            self.assertEqual(receipt["fit_status"], "unresolved")
            self.assertNotIn("secret", json.dumps(receipt))
            call.assert_called_once()
            self.assertFalse(self.qualify(p)["eligible_for_ranking"])

    def test_missing_receipt_stale_packet_and_forged_fit_are_not_passes(self):
        with self.assertRaises(jev.Invalid):
            self.qualify()
        self.decide(response("wrong_transformation"))
        receipt_path = self.root / "brief/1.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["fit_status"] = "pass"
        receipt_path.write_text(json.dumps(receipt))
        self.assertFalse(self.qualify()["eligible_for_ranking"])
        self.packet["unknowns"].append("changed evidence")
        with self.assertRaisesRegex(jev.Invalid, "stale_receipt"):
            self.qualify()

    def test_offline_cli_needs_neither_sdk_nor_key_and_exits_nonzero_on_rejection(self):
        packet_path, policy_path, gates_path = [self.root / name for name in ("packet.json", "policy.json", "gates.json")]
        for path, data in ((packet_path, self.packet), (policy_path, self.policy), (gates_path, self.gates)):
            path.write_text(json.dumps(data))
        args = [sys.executable, "-S", str(SCRIPT), "preflight", "--packet", str(packet_path), "--policy", str(policy_path)]
        env = {k: v for k, v in os.environ.items() if k != "TYPESAFE_API_KEY"}
        p = subprocess.run(args, capture_output=True, text=True, env=env, check=True)
        self.assertEqual(json.loads(p.stdout)["packet_sha256"], jev.digest(self.packet))
        self.decide(response("wrong_transformation"))
        args[3] = "qualify"
        args += ["--run-dir", str(self.root), "--gates", str(gates_path)]
        p = subprocess.run(args, capture_output=True, text=True, env=env)
        self.assertEqual(p.returncode, 1, p.stderr)
        self.assertFalse(json.loads(p.stdout)["eligible_for_ranking"])

    def test_duplicate_and_nonfinite_json_are_rejected(self):
        path = self.root / "invalid.json"
        for value in ('{"a":1,"a":2}', '{"a":NaN}'):
            path.write_text(value)
            with self.assertRaises(jev.Invalid):
                jev.read_json(path)

    def test_concurrent_call_cannot_consume_a_second_attempt(self):
        entered, release = threading.Event(), threading.Event()
        results = []

        def slow_call(*_):
            entered.set()
            self.assertTrue(release.wait(5))
            return response()

        thread = threading.Thread(target=lambda: results.append(jev.decide(
            self.packet, self.policy, self.root, jev.digest(self.packet), call=slow_call)))
        thread.start()
        try:
            self.assertTrue(entered.wait(5))
            call = Mock()
            with self.assertRaisesRegex(jev.Invalid, "attempt_incomplete"):
                jev.decide(self.packet, self.policy, self.root, jev.digest(self.packet), call=call)
            call.assert_not_called()
        finally:
            release.set()
            thread.join(5)
        self.assertEqual(len(results), 1)
        self.assertFalse((self.root / "brief/2.json").exists())

    def test_question_order_drift_and_invalid_receipts_fail_closed(self):
        self.decide(response())
        with patch.object(jev, "CRITERIA", dict(reversed(list(jev.CRITERIA.items())))):
            with self.assertRaisesRegex(jev.Invalid, "run_policy_drift"):
                self.qualify()
        (self.root / "brief/1.json").write_text("[]")
        with self.assertRaisesRegex(jev.Invalid, "invalid_receipt"):
            self.qualify()


if __name__ == "__main__":
    unittest.main()
