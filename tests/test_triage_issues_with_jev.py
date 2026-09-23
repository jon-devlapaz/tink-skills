"""Contract tests for the read-only Jev triage kernel. No network."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "triage-issues-with-jev"
SCRIPT = SKILL / "scripts" / "triage_kernel.py"


def load_kernel():
    spec = importlib.util.spec_from_file_location("triage_kernel", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


KERNEL = load_kernel()


class TestAuthority(unittest.TestCase):
    def test_triage_and_cleanup_do_not_grant_writes(self):
        self.assertFalse(KERNEL.writes_authorized("triage the backlog"))
        self.assertFalse(KERNEL.writes_authorized("clean up the issues"))
        self.assertFalse(KERNEL.writes_authorized("please organize and dedupe"))

    def test_explicit_grant_in_the_same_request(self):
        self.assertTrue(KERNEL.writes_authorized("I grant write authority to comment"))
        self.assertTrue(KERNEL.writes_authorized("you may close these issues"))
        self.assertTrue(KERNEL.writes_authorized("apply labels to the duplicates"))


class TestClaimSplitAndPairs(unittest.TestCase):
    def test_chunks_follow_headings_and_stay_few(self):
        body = "\n".join([
            "# Ledger",
            "- mandate a minimal ledger scratch format and location for the session",
            "- add minimal ledger fixtures plus a pre-intent example file",
            "# Unrelated",
            "A short note.",
        ])
        chunks = KERNEL.chunk_body("grill-me ledger", body)
        self.assertEqual(len(chunks), 2)
        self.assertIn("ledger scratch format", chunks[0])

    def test_shared_key_pairs_same_repo_only(self):
        cards = [
            {"card_id": "a", "repo": "tink-skills", "title": "skill-gate: --risk-threshold exit", "text": "skill-gate: --risk-threshold exit"},
            {"card_id": "b", "repo": "tink-skills", "title": "skill-gate: --risk-threshold verdict", "text": "skill-gate: --risk-threshold verdict"},
            {"card_id": "c", "repo": "tink", "title": "skill-gate: --risk-threshold elsewhere", "text": "skill-gate: --risk-threshold elsewhere"},
            {"card_id": "d", "repo": "tink-skills", "title": "Add a docs page", "text": "Add a docs page"},
        ]
        pairs = KERNEL.candidate_pairs(cards)
        self.assertEqual([pair["pair_id"] for pair in pairs], ["a|b"])

    def test_claim_threshold_keeps_orthogonal_chunks_as_cards(self):
        issues = [{
            "id": "78",
            "repo": "tink-skills",
            "number": 78,
            "title": "skill-gate: --risk-threshold changes the exit code but not the verdict",
            "chunks": [
                "exit code changes when the threshold moves",
                "a threshold above 0.5 still prints pass",
            ],
        }]
        result = KERNEL.apply_claims({"issues": issues, "claim_answers": {"78:0": 0.80, "78:1": 0.91}})
        self.assertEqual(len(result["cards"]), 2)
        self.assertEqual(result["cards"][0]["issue_id"], result["cards"][1]["issue_id"])

    def test_low_claim_falls_back_to_one_title_card(self):
        issues = [{
            "id": "1",
            "repo": "tink",
            "number": 1,
            "title": "Add tink info",
            "chunks": ["some background paragraph that is not its own criterion"],
        }]
        result = KERNEL.apply_claims({"issues": issues, "claim_answers": {"1:0": 0.20}})
        self.assertEqual([card["card_id"] for card in result["cards"]], ["1"])


class TestContractKernel(unittest.TestCase):
    def test_union_find_merges_only_combine(self):
        cards = [
            {"card_id": "a", "repo": "tink", "text": "skill-gate flag", "title": "skill-gate flag"},
            {"card_id": "b", "repo": "tink", "text": "skill-gate flag paraphrase", "title": "skill-gate flag paraphrase"},
            {"card_id": "c", "repo": "tink", "text": "skill-gate narrower case", "title": "skill-gate narrower case"},
        ]
        pairs = [
            {"pair_id": "a|b", "a": "a", "b": "b"},
            {"pair_id": "a|c", "a": "a", "b": "c"},
        ]
        applied = KERNEL.apply_pairs({
            "cards": cards,
            "pairs": pairs,
            "pair_answers": {
                "a|b__same": 0.93,
                "a|b__indep": 0.13,
                "a|c__same": 0.20,
                "a|c__indep": 0.90,
            },
        })
        kinds = {edge["pair_id"]: edge["kind"] for edge in applied["edges"]}
        self.assertEqual(kinds["a|b"], "COMBINE")
        self.assertEqual(kinds["a|c"], "SEPARATE")
        clusters = [set(group) for group in applied["clusters"]]
        self.assertIn({"a", "b"}, clusters)
        self.assertIn({"c"}, clusters)

    def test_mid_probabilities_review_and_do_not_merge(self):
        self.assertEqual(KERNEL.edge_kind(0.50, 0.50), "REVIEW")
        cards = [
            {"card_id": "a", "repo": "tink", "text": "x", "title": "x"},
            {"card_id": "b", "repo": "tink", "text": "y", "title": "y"},
        ]
        applied = KERNEL.apply_pairs({
            "cards": cards,
            "pairs": [{"pair_id": "a|b", "a": "a", "b": "b"}],
            "pair_answers": {"a|b__same": 0.69, "a|b__indep": 0.39},
        })
        self.assertEqual(applied["edges"][0]["kind"], "REVIEW")
        self.assertEqual(sorted(len(group) for group in applied["clusters"]), [1, 1])


class TestAcceptDeny(unittest.TestCase):
    def test_deny_questions_are_omitted_without_evidence(self):
        request = KERNEL.accept_request({"card": "a bug", "code_evidence": "", "policy_text": ""})
        self.assertNotIn("already", request["questions"])
        self.assertNotIn("out_of_scope", request["questions"])
        self.assertIn("bug", request["questions"])
        self.assertEqual(request["model"], "jev-1.13.0")

    def test_deny_requires_the_evidence_that_was_retrieved(self):
        hot = {"bug": 0.1, "enhancement": 0.1, "needs_info": 0.1, "already": 0.99, "out_of_scope": 0.99, "agent_ready": 0.1}
        self.assertEqual(
            KERNEL.disposition(hot, has_code=False, has_policy=False)["disposition"],
            "REVIEW",
        )
        self.assertEqual(
            KERNEL.disposition(hot, has_code=True, has_policy=False)["disposition"],
            "DENY_ALREADY_IMPLEMENTED",
        )
        self.assertEqual(
            KERNEL.disposition(hot, has_code=False, has_policy=True)["disposition"],
            "DENY_OUT_OF_SCOPE",
        )

    def test_category_conflict_stays_review(self):
        answers = {
            "bug": 0.80,
            "enhancement": 0.80,
            "needs_info": 0.10,
            "agent_ready": 0.90,
        }
        result = KERNEL.disposition(answers, has_code=False, has_policy=False)
        self.assertEqual(result["disposition"], "REVIEW")
        self.assertEqual(result["category"], "conflict")

    def test_accept_candidate_names_one_category(self):
        answers = {
            "bug": 0.20,
            "enhancement": 0.75,
            "needs_info": 0.20,
            "agent_ready": 0.80,
        }
        result = KERNEL.disposition(answers, has_code=False, has_policy=False)
        self.assertEqual(result, {"disposition": "ACCEPT_CANDIDATE", "category": "enhancement"})

    def test_out_of_scope_question_appears_when_policy_is_present(self):
        request = KERNEL.accept_request({
            "card": "dark mode",
            "code_evidence": "",
            "policy_text": "# Dark mode\n\nRejected.\n",
        })
        self.assertIn("out_of_scope", request["questions"])
        self.assertNotIn("already", request["questions"])


class TestSkillText(unittest.TestCase):
    def test_skill_shows_the_question_text_and_the_cuts(self):
        text = (SKILL / "SKILL.md").read_text()
        self.assertIn("name: triage-issues-with-jev", text)
        for question in (
            KERNEL.QUESTION_SAME,
            KERNEL.QUESTION_INDEP,
            KERNEL.QUESTION_IS_CLAIM,
            KERNEL.QUESTION_BUG,
            KERNEL.QUESTION_ENHANCEMENT,
            KERNEL.QUESTION_NEEDS_INFO,
            KERNEL.QUESTION_ALREADY,
            KERNEL.QUESTION_OUT_OF_SCOPE,
            KERNEL.QUESTION_AGENT_READY,
        ):
            self.assertIn(question, text)
        self.assertIn("jev-1.13.0", text)
        self.assertIn("same >= 0.70 and indep < 0.40", text)
        self.assertIn("already >= 0.80", text)
        self.assertNotIn("do not triage tickets you created", text.lower())
        self.assertNotIn("happier-github-ops", text)
        self.assertNotIn("TYPESAFE_API_KEY=", text)


if __name__ == "__main__":
    unittest.main()
