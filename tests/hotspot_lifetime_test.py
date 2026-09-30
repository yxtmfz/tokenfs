import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from hotspot_lifetime_analysis import analyze


def event(op, at, path='x', location=0, handle=0, tier='', size=0):
    return dict(op=op, start_ns=at, end_ns=at+1, path=path, location=location,
                handle=handle, tier=tier, bytes=size, selected_ns=at, wait_ns=0)


class LifetimeTest(unittest.TestCase):
    def fixture(self):
        events = [event('policy_PROMOTE_READY', 10, size=100),
                  event('open', 20, handle=1, tier='inflight'),
                  event('read', 21, handle=1, tier='inflight', size=100),
                  event('policy_EVICT', 30),
                  event('policy_PROMOTE_READY', 40, size=100),
                  event('open', 50, handle=2, tier='local'),
                  event('read', 51, handle=2, tier='local', size=40),
                  event('read', 52, handle=2, tier='local', size=60),
                  event('policy_EVICT', 60),
                  event('policy_PROMOTE_READY', 70, size=100)]
        return dict(clock='CLOCK_MONOTONIC', dropped=0, events=events), dict(
            read_open_count=2, read_local_bytes=100, read_inflight_bytes=100, copy_cost_samples=3)

    def test_ram_is_not_disk_and_open_tail_is_censored(self):
        t, m = self.fixture()
        r = analyze(t, m)
        self.assertEqual((r['copies'], r['closed'], r['censored']), (3, 2, 1))
        self.assertEqual(r['closed_zero_disk_reads'], 1)
        self.assertEqual(r['closed_zero_with_ram_reads'], 1)
        self.assertEqual(r['disk_reads'], 1)  # two FUSE chunks, one logical read

    def test_missing_or_corrupt_evidence_rejected(self):
        t, m = self.fixture()
        for field, value in [('dropped', 1), ('clock', 'wall')]:
            broken = copy.deepcopy(t); broken[field] = value
            with self.assertRaises(ValueError): analyze(broken, m)
        for field in ['copy_cost_samples', 'read_local_bytes', 'read_open_count']:
            broken = dict(m); broken[field] += 1
            with self.assertRaises(ValueError): analyze(t, broken)

    def test_unmatched_disk_hit_not_classified_as_zero_benefit(self):
        t, m = self.fixture()
        # An open racing the READY marker cannot be assigned confidently.
        t['events'][5]['selected_ns'] = 35
        t['events'][5]['start_ns'] = 35
        r = analyze(t, m)
        self.assertEqual(r['unmatched_local_handles'], [2])
        self.assertEqual(r['closed_zero_disk_reads'], 0)

    def test_duplicate_ready_and_missing_read_open_rejected(self):
        t, m = self.fixture()
        t['events'].append(event('policy_PROMOTE_READY', 25, size=100))
        with self.assertRaises(ValueError): analyze(t, m)
        t, m = self.fixture()
        t['events'][2]['handle'] = 999
        with self.assertRaises(ValueError): analyze(t, m)


if __name__ == '__main__': unittest.main()
