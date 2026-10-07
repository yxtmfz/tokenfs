#!/usr/bin/env python3
"""Observed disk-copy lifetimes, not counterfactual speedups or net-benefit labels."""
import argparse
from collections import defaultdict
import json
from pathlib import Path

READY = {'policy_PROMOTE_READY', 'policy_REPLICATE_READY'}


def analyze(trace, metrics):
    if trace.get('clock') != 'CLOCK_MONOTONIC' or trace.get('dropped') != 0:
        raise ValueError('incomplete or incompatible trace')
    events = trace['events']
    for e in events:
        if not 0 < e['start_ns'] <= e['end_ns']:
            raise ValueError('invalid event clock')
    lifetimes = []
    active = {}
    for e in sorted(events, key=lambda e: e['start_ns']):
        key = (e['path'], e['location'])
        if e['op'] in READY:
            if key in active:
                raise ValueError('duplicate READY without eviction')
            row = dict(path=e['path'], location=e['location'], ready_ns=e['start_ns'],
                       end_ns=None, bytes=e['bytes'], disk_reads=0, disk_bytes=0,
                       inflight_reads=0, uncertain=False)
            active[key] = row
            lifetimes.append(row)
        elif e['op'] == 'policy_EVICT':
            if key not in active:
                raise ValueError('eviction without READY: requires empty initial cache')
            active.pop(key)['end_ns'] = e['start_ns']
    opens = {e['handle']: e for e in events if e['op'] == 'open' and e['handle']}
    if len(opens) != metrics.get('read_open_count', 0):
        raise ValueError('open count mismatch')
    read_bytes = defaultdict(int)
    positive_handles = set()
    for e in events:
        if e['op'] != 'read':
            continue
        if e['handle'] not in opens:
            raise ValueError('read without open')
        if e['tier'] != opens[e['handle']]['tier']:
            raise ValueError('read tier changed')
        read_bytes[e['handle']] += e['bytes']
        if e['bytes']:
            positive_handles.add(e['handle'])
    tiers = {tier: sum(read_bytes[h] for h, e in opens.items() if e['tier'] == tier)
             for tier in ['local', 'remote', 'inflight']}
    if any(v != metrics.get('read_' + k + '_bytes', 0) for k, v in tiers.items()):
        raise ValueError('tier byte mismatch')
    if len(lifetimes) != metrics.get('copy_cost_samples', 0):
        raise ValueError('committed-copy count mismatch')
    unmatched = []
    for handle, e in opens.items():
        if handle not in positive_handles or e['tier'] not in ['local', 'inflight']:
            continue
        at = e['selected_ns']
        if not e['start_ns'] <= at <= e['end_ns']:
            raise ValueError('missing or invalid source-selection time')
        matches = [r for r in lifetimes if r['path'] == e['path'] and
                   (e['tier'] == 'inflight' or r['location'] == e['location']) and
                   r['ready_ns'] <= at and (r['end_ns'] is None or at < r['end_ns'])]
        if e['tier'] == 'local':
            if len(matches) == 1:
                matches[0]['disk_reads'] += 1
                matches[0]['disk_bytes'] += read_bytes[handle]
            else:
                # Metadata publication and its diagnostic marker are separate.
                # Do not call a zero-hit copy wasteful when attribution is uncertain.
                unmatched.append(handle)
                for r in lifetimes:
                    if r['path'] == e['path']:
                        r['uncertain'] = True
        else:
            for r in matches:
                r['inflight_reads'] += 1
    closed = [r for r in lifetimes if r['end_ns'] is not None]
    known_closed = [r for r in closed if not r['uncertain']]
    zero = [r for r in known_closed if not r['disk_reads']]
    plans = [e for e in events if e['op'] == 'shared_plan']
    attempts = [e for e in events if e['op'] == 'copy_attempt']
    return dict(copies=len(lifetimes), closed=len(closed), censored=len(active),
                closed_zero_disk_reads=len(zero), closed_with_disk_reads=sum(r['disk_reads'] > 0 for r in known_closed),
                closed_zero_with_ram_reads=sum(r['inflight_reads'] > 0 for r in zero),
                closed_zero_without_ram_reads=sum(r['inflight_reads'] == 0 for r in zero),
                unmatched_local_handles=unmatched, disk_reads=sum(r['disk_reads'] for r in lifetimes),
                bytes_by_tier=tiers, planning_attempts=len(plans),
                rejected_plans=sum(e['tier'] != 'selected' for e in plans),
                planning_ms=sum(e['end_ns'] - e['start_ns'] for e in plans) / 1e6,
                copy_attempts=len(attempts), copy_wait_ms=sum(e['wait_ns'] for e in attempts) / 1e6,
                # Overlapping durations: not additive wall-clock attribution.
                copy_attempt_ms=sum(e['end_ns'] - e['start_ns'] for e in attempts) / 1e6,
                lifetimes=lifetimes)


def analyze_case(case):
    return analyze(json.loads((case / 'request-trace.json').read_text()),
                   json.loads((case / 'result.json').read_text())['metrics'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('case', type=Path)
    a = p.parse_args()
    print(json.dumps(analyze_case(a.case), indent=2))
