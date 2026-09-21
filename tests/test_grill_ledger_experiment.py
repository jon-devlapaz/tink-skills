"""Counterexamples for the evaluation-only prototype, not prompt enforcement."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import unittest

PATH = Path(__file__).resolve().parents[1] / 'skills/grill-me-with-jev/evals/ledger_experiment.py'
SPEC = importlib.util.spec_from_file_location('grill_ledger_experiment', PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
Ledger, Node = MODULE.Ledger, MODULE.Node


class LedgerExperimentTests(unittest.TestCase):
    def test_cycle_rejected_atomically(self):
        ledger = Ledger()
        ledger.put(Node('A'))
        ledger.put(Node('B', prerequisites=('A',)))
        before = ledger.nodes, ledger.revision
        with self.assertRaisesRegex(ValueError, 'cycle'):
            ledger.put(Node('A', prerequisites=('B',)))
        self.assertEqual(before, (ledger.nodes, ledger.revision))

    def test_parked_and_unknown_nodes_block_confirmation(self):
        ledger = Ledger()
        ledger.put(Node('A', recommendation='Strong recommendation, still unanswered'))
        ledger.put(Node('B', prerequisites=('A',)))
        ledger.put(Node('C', active=None))
        self.assertEqual(ledger.ready(), {'A'})
        self.assertEqual(ledger.blockers(), {'A', 'B', 'C'})
        with self.assertRaises(ValueError):
            ledger.confirm(ledger.revision)

    def test_changed_parent_dirties_transitive_descendants_without_changing_answers(self):
        ledger = Ledger()
        for node in [Node('A', 'settled', answer='old', authority='user'),
                     Node('B', 'settled', ('A',), answer='B value', authority='user'),
                     Node('C', 'settled', ('B',), answer='C value', authority='user'),
                     Node('D', 'settled', answer='independent', authority='user')]:
            ledger.put(node)
        ledger.confirm(ledger.revision)
        self.assertEqual(ledger.put(replace(ledger.nodes['A'], answer='new')), {'B', 'C'})
        self.assertEqual(ledger.dirty, {'B', 'C'})
        self.assertEqual(ledger.nodes['B'].answer, 'B value')
        self.assertEqual(ledger.nodes['D'].answer, 'independent')
        self.assertIsNone(ledger.confirmed)
        ledger.reassess('B', ledger.nodes['B'])
        ledger.reassess('C', replace(ledger.nodes['C'], status='unresolved', answer=None))
        self.assertEqual(ledger.ready(), {'C'})
        self.assertEqual(ledger.blockers(), {'C'})

    def test_noop_does_not_invalidate_confirmation(self):
        ledger = Ledger()
        node = Node('A', 'settled', answer='chosen', authority='user')
        ledger.put(node)
        ledger.confirm(ledger.revision)
        rev = ledger.revision
        self.assertEqual(ledger.put(node), set())
        self.assertEqual((ledger.revision, ledger.confirmed), (rev, rev))

    def test_recommendation_never_replaces_actual_answer(self):
        ledger = Ledger()
        ledger.put(Node('A', 'settled', recommendation='Redis', answer='Postgres', authority='user'))
        self.assertEqual(ledger.nodes['A'].answer, 'Postgres')
        with self.assertRaisesRegex(ValueError, 'missing_answer_authority'):
            ledger.put(Node('B', 'settled', recommendation='Redis'))

    def test_deferring_parent_does_not_discard_child(self):
        ledger = Ledger()
        ledger.put(Node('A', 'deferred', defer_reason='Later release', revisit='Next release'))
        ledger.put(Node('B', prerequisites=('A',)))
        self.assertFalse(ledger.ready())
        self.assertEqual(ledger.blockers(), {'B'})

    def test_inactive_parent_does_not_unlock_child(self):
        ledger = Ledger()
        ledger.put(Node('A', 'settled', active=False, answer='old', authority='user'))
        ledger.put(Node('B', prerequisites=('A',)))
        self.assertFalse(ledger.ready())
        self.assertEqual(ledger.blockers(), {'A', 'B'})

    def test_mutable_edges_rejected(self):
        ledger = Ledger()
        with self.assertRaisesRegex(ValueError, 'invalid_prerequisites'):
            ledger.put(Node('A', prerequisites=[]))
        self.assertEqual(ledger.revision, 0)

    def test_stale_confirmation_rejected(self):
        ledger = Ledger()
        ledger.put(Node('A', 'settled', answer='chosen', authority='user'))
        with self.assertRaisesRegex(ValueError, 'stale'):
            ledger.confirm(ledger.revision - 1)

    def test_mutating_snapshot_does_not_change_ledger(self):
        ledger = Ledger()
        ledger.put(Node('A'))
        ledger.nodes.clear()
        self.assertEqual(ledger.blockers(), {'A'})


if __name__ == '__main__':
    unittest.main()
