#!/usr/bin/env python3
"""Read-only decomposition of the frozen 80 moving diagnostic, never formal rates."""
import csv, hashlib, json, math
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parent
RAW=BASE.parent/'moving-trace-evidence'
ARMS=('Full','NoHotspot')
rows={a:list(csv.DictReader((BASE/(a+'-requests.csv')).open())) for a in ARMS}
res={a:json.loads((RAW/a/'result.json').read_text()) for a in ARMS}
ev={a:json.loads((RAW/a/'request-trace.json').read_text())['events'] for a in ARMS}
oldhash=json.loads((BASE.parent/'moving-trace-inputhashes-independent.json').read_text())
newhash={str(p.relative_to(RAW)):hashlib.sha256(p.read_bytes()).hexdigest() for p in RAW.rglob('*') if p.is_file()}
assert oldhash==newhash and len(newhash)==27
assert all(len(v)==1152 for v in rows.values())
for x,y in zip(*rows.values()):
 assert all(x[k]==y[k] for k in ('index','key','caller','occurrence','access_class'))
 assert all(x[k]=='' and y[k]=='' for k in ('physical_pread_ops','physical_pread_bytes'))
def total(a,k): return math.fsum(float(r[k]) for r in rows[a])
def delta(k): return total('Full',k)-total('NoHotspot',k)
# These four components exactly partition response; timings for overlapped
# callbacks / background work below are descriptive, never added to this sum.
components={k:delta(k) for k in ('client_open_ms','client_read_ms','client_close_ms','ipc_scheduling_ms')}
response_delta=delta('response_ms')
assert abs(sum(components.values())-response_delta)<1e-8
wall_delta=(res['Full']['job_wall_s']-res['NoHotspot']['job_wall_s'])*1000
read_breakdown={'pread_ms':delta('pread_ms'),
 'daemon_read_non_pread_ms':delta('read_non_pread_ms'),
 'client_read_minus_daemon_read_ms':delta('client_read_ms')-delta('daemon_read_ms')}
assert abs(sum(read_breakdown.values())-components['client_read_ms'])<1e-8
strata={}
for group in sorted({r['access_class']+'/'+r['tier'] for r in rows['Full']}):
 access,tier=group.split('/')
 rs={a:[r for r in rows[a] if r['access_class']==access and r['tier']==tier] for a in ARMS}
 assert len(rs['Full'])==len(rs['NoHotspot'])
 strata[group]={'n':len(rs['Full']),'response_delta_sum_ms':math.fsum(float(r['response_ms']) for r in rs['Full'])-math.fsum(float(r['response_ms']) for r in rs['NoHotspot']),
  'pread_delta_sum_ms':math.fsum(float(r['pread_ms']) for r in rs['Full'])-math.fsum(float(r['pread_ms']) for r in rs['NoHotspot'])}
assert sum(x['n'] for x in strata.values())==1152
assert abs(sum(x['response_delta_sum_ms'] for x in strata.values())-response_delta)<1e-8
r844={a:{k:rows[a][844][k] for k in ('index','key','caller','tier','access_class','response_ms','client_open_ms','client_read_ms','pread_ms','read_non_pread_ms','copy_pipeline_overlap_ms','copy_attempt_overlap_ms','shared_plan_overlap_ms')} for a in ARMS}
peak_delta=float(r844['Full']['response_ms'])-float(r844['NoHotspot']['response_ms'])
tops={a:sorted(rows[a],key=lambda r:float(r['response_ms']),reverse=True)[:12] for a in ARMS}
for a in ARMS: assert all(r['tier']=='remote' and r['access_class']=='first' for r in tops[a])
report={
 'diagnosis_only':True,'performance_evidence':False,'raw_27_hashes_unchanged':True,
 'binary_sha256':'f5e2981b8b4f0ce54bb2994e53998608de4cec4a3c861531e8e86e0aab031f71',
 'request_count_per_arm':1152,
 'same_ordinal_tier_mismatches':sum(x['tier']!=y['tier'] for x,y in zip(*rows.values())),
 'same_ordinal_location_mismatches':sum(x['location']!=y['location'] for x,y in zip(*rows.values())),
 'metrics':{a:{k:res[a]['metrics'].get(k,0) for k in ('open_remote','open_local','open_inflight','direct_backend_pread_ops','direct_backend_pread_bytes','read_fill_copy_count','read_fill_copy_bytes','read_release_count','shared_placement_plans','copy_cost_planning_us','submission_precheck_us','replica_touch_batched','peer_cache_hit','cross_gpu_local_replica_hit')} for a in ARMS},
 'wall_delta_ms':wall_delta,'response_sum_delta_ms':response_delta,
 'controller_loop_residual_delta_ms':wall_delta-response_delta,
 'additive_response_components_delta_ms':components,
 'additive_client_read_components_delta_ms':read_breakdown,
 'strata':strata,'index844':r844,
 'index844_response_delta_ms':peak_delta,'index844_response_delta_over_wall_delta':peak_delta/wall_delta,
 'index844_read_callbacks':{a:[{k:e[k] for k in ('op','bytes','pread_ns','start_ns','end_ns')} for e in ev[a] if e['handle']==845 and e['op']=='read'] for a in ARMS},
 'p99_ordinal':{a:int(tops[a][-1]['index']) for a in ARMS},
 'p99_ms':{a:float(tops[a][-1]['response_ms']) for a in ARMS},
 'index776_response_ms':{a:float(rows[a][776]['response_ms']) for a in ARMS},
 'top12_all_first_remote':True,
 'top12_overlaps_ms':{a:{k:math.fsum(float(r[k]) for r in tops[a]) for k in ('copy_pipeline_overlap_ms','copy_attempt_overlap_ms','shared_plan_overlap_ms','all_release_overlap_ms')} for a in ARMS},
 'event_spans_ms':{a:{op:math.fsum(e['end_ns']-e['start_ns'] for e in ev[a] if e['op']==op)/1e6 for op in ('shared_plan','copy_attempt','copy_pipeline')} for a in ARMS},
 'boundaries':[
 'Aggregate physical counters match; per-request physical ops, bytes, and offsets are unavailable and remain null.',
 'pread elapsed intervals can contain scheduling and backend waits; this trace cannot identify their underlying cause.',
 'Overlapping callback and background durations are not additive wall-time cost.',
 'Index 844 is retained in every statistic. Its paired excess describes this diagnostic only, not a corrected formal result.',
 'First-read top12 does not prove every tail in other inputs/runs is a first read.',
 'Equal backend tier sequence is not equal GPU-domain placement: 44 local request locations differ.',
 'Single diagnostic pair does not estimate a stable performance effect or confidence interval.'
 ]}
(BASE/'decomposition.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('wall_delta_ms','response_sum_delta_ms','controller_loop_residual_delta_ms','additive_response_components_delta_ms','additive_client_read_components_delta_ms','strata','p99_ordinal','p99_ms','index776_response_ms','top12_overlaps_ms')},indent=2))
