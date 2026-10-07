#!/usr/bin/env python3
"""Describe every frozen run and pair without changing acceptance or raw data."""
from pathlib import Path
import json,hashlib,statistics,math
root=Path(__file__).resolve().parents[1]
load=lambda p:json.loads(p.read_text())
MIB=1024*1024
rows=load(root/'validation/results/mechanisms.json');indexed={(r['block'],r['strategy']):r for r in rows}
observations=[]
for row in rows:
    case=root/'data/development'/row['block']/row['strategy'];r=load(case/'result.json');m=r['metrics'];requests=load(case/'requests.json')
    seen=set();first=[];reused=[]
    for x in requests:
        (reused if x['key'] in seen else first).append(x['response_seconds']);seen.add(x['key'])
    descending=sorted(requests,key=lambda x:x['response_seconds'],reverse=True)
    precheck={key.removeprefix('submission_precheck_'):value for key,value in m.items() if key.startswith('submission_precheck_')}
    precheck['mean_attempt_us']=precheck.get('us',0)/max(1,precheck.get('attempts',0))
    precheck['counter_wall_fraction_pct']=precheck.get('us',0)/1e6/r['job_wall_s']*100
    environment=load(case/'environment.json')
    observations.append(dict(block=row['block'],strategy=row['strategy'],
        service_requests={tier:m.get(tier+'_read_open_count',0) for tier in ['remote','local','inflight']},
        read_release_count=m['read_release_count'],background_submitted=m.get('background_submitted',0),background_completed=m.get('background_completed',0),
        wall_s=r['job_wall_s'],drain_s=r['drain_s'],completed_with_background_s=r['completed_with_background_s'],daemon_cpu_s=r['daemon_cpu_s'],
        copies=row['completed_copies'],physical_pread_ops=row['physical_pread_ops'],physical_pread_bytes=row['physical_pread_bytes'],
        action_sha256=row['action_sha256'],read_latency_total_s=m.get('read_latency_us_total',0)/1e6,
        precheck=precheck,shared_placement_plans=m.get('shared_placement_plans',0),
        shared_placement_selected=m.get('shared_placement_selected',0),shared_placement_no_gain=m.get('shared_placement_no_gain',0),
        affinity_receipts={phase:environment[phase]['cpu_affinity'] for phase in ['before','after']},
        loadavg={phase:environment[phase]['loadavg'] for phase in ['before','after']},
        tail_payload_peak_bytes=m.get('direct_read_tail_buffer_bytes_peak',0),capture_payload_peak_bytes=m.get('read_fill_buffer_peak_bytes',0),
        first_count=len(first),reused_count=len(reused),first_response_mean_ms=statistics.mean(first)*1000 if first else None,
        reused_response_mean_ms=statistics.mean(reused)*1000 if reused else None,
        p99_neighbors=[dict(rank_from_slowest=i+1,index=descending[i]['index'],key=descending[i]['key'],response_ms=descending[i]['response_seconds']*1000) for i in [10,11,12]],
        slowest=dict(index=descending[0]['index'],response_ms=descending[0]['response_seconds']*1000)))
obs={(r['block'],r['strategy']):r for r in observations};comparisons=[]
for p in load(root/'validation/results/pairs.json'):
    x=obs[(p['block'],p['treatment'])];y=obs[(p['block'],p['baseline'])]
    comparisons.append(dict(block=p['block'],baseline=p['baseline'],primary=p['primary_comparison'],throughput_gain_pct=p['throughput_gain_pct'],p99_reduction_pct=p['p99_reduction_pct'],drain_gain_pct=p['drain_gain_pct'],full_acceptance=p['full_acceptance'],
        service_requests=dict(Full=x['service_requests'],baseline=y['service_requests']),copies=dict(Full=x['copies'],baseline=y['copies']),
        same_aggregate_io_work=all(x[k]==y[k] for k in ['service_requests','copies','physical_pread_ops','physical_pread_bytes']),
        same_actions=x['action_sha256']==y['action_sha256'],background_tasks=dict(Full=x['background_submitted'],baseline=y['background_submitted']),
        wall_difference_s=y['wall_s']-x['wall_s'],daemon_cpu_difference_s=y['daemon_cpu_s']-x['daemon_cpu_s'],
        read_counter_difference_s=y['read_latency_total_s']-x['read_latency_total_s'],
        precheck=dict(Full=x['precheck'],baseline=y['precheck']),
        planning=dict(Full=x['shared_placement_plans'],baseline=y['shared_placement_plans'])))
answer=dict(diagnosis_only=True,acceptance_unchanged=True,requests_not_independent_replicates=True,
    warning='Matching aggregate I/O counts is not equality of every timestamp, routing sequence or external condition. Counters omit Read postprocessing; cumulative spans/counters, including precheck_us, are not causal wall-time savings. CPU affinity constrains placement, not exclusive cores or frequency. Only same-batch NoIndexedPrecheck controls the index implementation; do not substitute batch79 timings. Two rounds do not establish significance.',runs=observations,comparisons=comparisons)
(root/'validation/mechanism-diagnosis.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(dict(runs=len(observations),comparisons=len(comparisons),primary_failures=sum(p['primary'] and not p['full_acceptance'] for p in comparisons))))
