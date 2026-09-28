"""User-revised criterion: positive measured throughput, without a 5% floor.
Historical frozen reports are immutable; this is a separate, explicitly revised screen.
"""
import math

def passes(pair):
    values=[pair[k] for k in ['gain_pct','p99_change_pct','drain_gain_pct']]
    return (all(math.isfinite(v) for v in values) and pair['gain_pct']>0 and
            pair['p99_change_pct']<=0 and pair['drain_gain_pct']>=0 and
            bool(pair['mechanism_active']) and
            (pair['baseline']=='PoolSIEVE1' or bool(pair['executed_actions_changed'])))
