import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import evidence_benchmark as benchmark


class ReleaseFenceTest(unittest.TestCase):
    def test_old_equal_counters_do_not_hide_last_pending_submission(self):
        snapshots = [
            dict(background_submitted=2, background_completed=2, read_release_count=9),
            dict(background_submitted=3, background_completed=2, read_release_count=10),
            dict(background_submitted=3, background_completed=3, read_release_count=10),
        ]
        with patch.object(benchmark, 'metrics', side_effect=snapshots) as observed, \
             patch.object(benchmark.time, 'monotonic', side_effect=[0, 0, .02, .04, .05]), \
             patch.object(benchmark.time, 'sleep') as pause:
            self.assertEqual(benchmark.drain('unused', expected_releases=10), .05)
            self.assertEqual(observed.call_count, 3)
            self.assertEqual(pause.call_count, 2)

    def test_missing_fence_times_out_even_when_both_counters_are_zero(self):
        with patch.object(benchmark, 'metrics', return_value={}), \
             patch.object(benchmark.time, 'monotonic', side_effect=[0, 0, 121]), \
             patch.object(benchmark.time, 'sleep'):
            with self.assertRaises(TimeoutError):
                benchmark.drain('unused', expected_releases=1)

    def test_duplicate_release_and_background_error_are_rejected(self):
        for snapshot in [dict(read_release_count=2),
                         dict(read_release_count=1, background_error_count=1)]:
            with patch.object(benchmark, 'metrics', return_value=snapshot):
                with self.assertRaises(RuntimeError):
                    benchmark.drain('unused', expected_releases=1)

    def test_older_frozen_protocol_without_release_counter_remains_supported(self):
        with patch.object(benchmark, 'metrics', return_value={}), \
             patch.object(benchmark.time, 'monotonic', side_effect=[0, 0, .01]):
            self.assertEqual(benchmark.drain('unused'), .01)


if __name__ == '__main__':
    unittest.main()
