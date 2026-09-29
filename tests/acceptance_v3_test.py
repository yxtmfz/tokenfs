import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from acceptance_v3 import BASELINES, passes, screen_matrix


class StrictDualMetricTest(unittest.TestCase):
    def setUp(self):
        self.pairs = [dict(block=b, baseline=v, gain_pct=1.0, p99_change_pct=-1.0,
                           drain_gain_pct=1.0, mechanism_active=True, executed_actions_changed=True)
                      for b in ('r1', 'r2') for v in BASELINES]

    def test_requires_all_eight_pairs(self):
        self.assertTrue(screen_matrix(self.pairs, ['r1', 'r2'])['passed'])
        for i in range(8):
            pairs = copy.deepcopy(self.pairs)
            pairs[i]['p99_change_pct'] = .001
            self.assertFalse(screen_matrix(pairs, ['r1', 'r2'])['passed'])

    def test_ties_nonfinite_and_missing_metrics_rejected(self):
        for key in ('gain_pct', 'p99_change_pct'):
            for value in (0, float('nan'), float('inf'), True, None):
                pair = dict(self.pairs[0], **{key: value})
                self.assertFalse(passes(pair), (key, value))
            pair = self.pairs[0].copy()
            del pair[key]
            self.assertFalse(passes(pair))

    def test_existing_checks_preserved(self):
        for change in [dict(drain_gain_pct=-.1), dict(mechanism_active=False),
                       dict(executed_actions_changed=False)]:
            self.assertFalse(passes(dict(self.pairs[0], **change)))

    def test_missing_duplicate_extra_and_same_round_rejected(self):
        for pairs in [self.pairs[:-1], self.pairs + [self.pairs[0]],
                      self.pairs[:-1] + [dict(self.pairs[-1], baseline='other')]]:
            with self.assertRaises(ValueError):
                screen_matrix(pairs, ['r1', 'r2'])
        with self.assertRaises(ValueError):
            screen_matrix(self.pairs, ['r1', 'r1'])


if __name__ == '__main__':
    unittest.main()
