"""Strict dual-metric screen; historical v2 reports retain their original criteria.

Every pair must improve throughput AND lower p99. A tie is not an improvement.
This development screen is not a statistical significance test.
"""
import math
from acceptance_v2 import passes as previous_passes

BASELINES = ('NoHotspot', 'NoAffinity', 'NoJoint', 'PoolSIEVE1')


def passes(pair):
    for key in ('gain_pct', 'p99_change_pct', 'drain_gain_pct'):
        value = pair.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not math.isfinite(value):
            return False
    if not all(key in pair for key in ('baseline', 'mechanism_active', 'executed_actions_changed')):
        return False
    return previous_passes(pair) and pair['p99_change_pct'] < 0


def screen_matrix(pairs, expected_blocks):
    if len(expected_blocks) != 2 or len(set(expected_blocks)) != 2:
        raise ValueError('Exactly two distinct frozen rounds are required')
    expected = {(b, v) for b in expected_blocks for v in BASELINES}
    seen = set()
    failures = []
    for pair in pairs:
        identity = (pair.get('block'), pair.get('baseline'))
        if identity not in expected or identity in seen:
            raise ValueError('Unexpected or duplicate comparison')
        seen.add(identity)
        if not passes(pair):
            failures.append(dict(block=identity[0], baseline=identity[1]))
    if seen != expected:
        raise ValueError('Incomplete two-round four-comparison matrix')
    return dict(criterion='throughput > 0%; p99 change < 0%; existing drain/mechanism checks retained',
                comparisons=8, passing_comparisons=8-len(failures),
                passed=not failures, failures=failures, statistical_confirmation=False)
