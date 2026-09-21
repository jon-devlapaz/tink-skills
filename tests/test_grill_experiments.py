"""Offline checks for experiment data/measurement boundaries, no model calls."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1] / 'skills/grill-me-with-jev/evals'
SPEC = importlib.util.spec_from_file_location('grill_experiments', BASE / 'run_experiments.py')
EXPERIMENTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPERIMENTS)


class ExperimentTests(unittest.TestCase):
    def test_choice_rejects_bad_distributions_and_mismatched_winner(self):
        valid = {'type': 'choice', 'choice': 'ask', 'confidence': .5,
                 'probabilities': {'ask': .8, 'investigate': .1, 'continue': .1}}
        self.assertTrue(EXPERIMENTS.valid_answer(valid, 'choice'))
        self.assertFalse(EXPERIMENTS.valid_answer({**valid, 'choice': 'continue'}, 'choice'))
        for value in [float('nan'), float('inf'), True, -1, 2]:
            bad = {**valid, 'probabilities': {**valid['probabilities'], 'ask': value}}
            self.assertFalse(EXPERIMENTS.valid_answer(bad, 'choice'))

    def test_noul_is_scalar_probability_not_fabricated_confidence(self):
        self.assertTrue(EXPERIMENTS.valid_answer({'type': 'noul', 'noul': .81}, 'noul'))
        self.assertFalse(EXPERIMENTS.valid_answer({'type': 'noul', 'confidence': .81}, 'noul'))
        self.assertFalse(EXPERIMENTS.valid_answer({'type': 'noul', 'noul': True}, 'noul'))

    def test_nontransient_failures_are_not_retried(self):
        for error in ['http_401', 'invalid_json', 'missing_key']:
            with self.subTest(error=error), patch.object(EXPERIMENTS, 'provider_once', return_value={'error': error}) as call:
                self.assertEqual(EXPERIMENTS.provider({}, 'noul')['error'], error)
                self.assertEqual(call.call_count, 1)

    def test_transient_failure_retried_once_with_receipts(self):
        with patch.object(EXPERIMENTS, 'provider_once', side_effect=[
                {'error': 'http_529', 'seconds': .1}, {'answers': {}, 'seconds': .1}]) as call, \
                patch.object(EXPERIMENTS.time, 'sleep'):
            result = EXPERIMENTS.provider({}, 'noul')
            self.assertEqual(call.call_count, 2)
            self.assertEqual(len(result['attempts']), 2)
            self.assertNotIn('error', result)

    def test_activation_near_neighbors_and_unique_ids(self):
        cases = json.loads((BASE / 'activation.json').read_text())['cases']
        self.assertEqual(len(cases), len({c['id'] for c in cases}))
        self.assertEqual({c['activate'] for c in cases}, {True, False})
        self.assertTrue(any('no interview' in c['prompt'] and not c['activate'] for c in cases))

    def test_replay_oracle_covers_questions_and_factual_investigations(self):
        for case in json.loads((BASE / 'ablation.json').read_text())['cases']:
            ids = {c['id'] for c in case['concerns']}
            oracle = case['oracle']
            self.assertTrue(set(oracle['required']) <= oracle['answers'].keys() <= ids)
            self.assertTrue(set(oracle['investigate']) <= oracle['facts'].keys() <= ids)
            self.assertFalse(set(oracle['required']) & set(oracle['unnecessary']))


if __name__ == '__main__':
    unittest.main()
