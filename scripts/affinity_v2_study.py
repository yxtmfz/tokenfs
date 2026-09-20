#!/usr/bin/env python3
"""Affinity-only real-storage study; legacy, disabled and common-window demand."""
from __future__ import annotations
import argparse,json,math,random,statistics
from pathlib import Path
import affinity_joint_study as core
from evidence_benchmark import dump
from evidence_report import interval,paired_p,holm
VARIANTS=['P-off','P-old','P-new']
SCENES=core.SCENES+['domain_return']
SOURCES=core.SOURCES+['scripts/affinity_v2_study.py']
original_config=core.configuration
original_trace=core.trace

def configuration(name,case,remote,quota,direct):
    cfg=original_config('J-no-P' if name=='P-off' else 'J',case,remote,quota,direct)
    cfg['policy']['measured_affinity_recent_demand']=name!='P-old'
    return cfg

def trace(block):
    if block['scenario']!='domain_return':return original_trace(block)
    rng=random.Random(block['seed']);events=[]
    for i in range(block['requests']):
        phase=min(3,4*i//block['requests']);caller=phase%3
        key=phase*6+rng.randrange(6) if rng.random()<.85 else rng.randrange(32,64)
        events.append(dict(index=i,key=key,caller=caller,bytes=block['shard_mib']*1048576))
    return events

def report(root):
    activate()
    a=core.audit(root)
    if not a['passed']:raise ValueError('incomplete affinity batch')
    m=json.loads((root/'manifest.json').read_text())
    if m['verify']:raise ValueError('content checks are not speed evidence')
    results={(p.parent.parent.name,p.parent.name):json.loads(p.read_text()) for p in root.glob('*/*/result.json')}
    summary=[];comparisons=[]
    for scene in SCENES:
        blocks=[b for b in m['spec']['blocks'] if b['scenario']==scene]
        if not blocks:continue
        for name in VARIANTS:
            rs=[results[b['id'],name] for b in blocks]
            summary.append(dict(scenario=scene,strategy=name,n=len(rs),mib_s=statistics.mean(r['effective_mib_s'] for r in rs),
                wall_s=statistics.mean(r['job_wall_s'] for r in rs),with_drain_s=statistics.mean(r['completed_with_background_s'] for r in rs),
                copy_mib=statistics.mean(sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/1048576 for r in rs),
                remote_mib=statistics.mean(r['metrics'].get('read_remote_bytes',0)/1048576 for r in rs),
                p99_ms=statistics.mean(r['request_p99_s']*1000 for r in rs),cpu_s=statistics.mean(r['daemon_cpu_s'] for r in rs),
                adjusted_plans=statistics.mean(r['metrics'].get('measured_affinity_reweighted_plans',0) for r in rs),
                share_vetoes=statistics.mean(r['metrics'].get('measured_precheck_affinity',0)+r['metrics'].get('measured_commit_affinity',0) for r in rs)))
        for baseline,family in [('P-off','new_vs_disabled'),('P-old','new_vs_legacy')]:
            pairs=[(results[b['id'],'P-new'],results[b['id'],baseline]) for b in blocks]
            logs=[math.log(a['job_wall_s']/b['job_wall_s']) for a,b in pairs]
            comparisons.append(dict(scenario=scene,baseline=baseline,treatment='P-new',family=family,n=len(pairs),
                time_ratio=math.exp(statistics.mean(logs)),ci95=interval(logs,math.exp),p_raw=paired_p(logs),p_holm=None,
                with_drain_ratio=math.exp(statistics.mean(math.log(a['completed_with_background_s']/b['completed_with_background_s']) for a,b in pairs)),
                baseline_mib_s=statistics.mean(b['effective_mib_s'] for a,b in pairs),new_mib_s=statistics.mean(a['effective_mib_s'] for a,b in pairs),
                mechanism_active_pairs=sum(a['metrics'].get('measured_affinity_reweighted_plans',0)>0 for a,b in pairs)))
    for family in ['new_vs_disabled','new_vs_legacy']:holm([c for c in comparisons if c['family']==family])
    for c in comparisons:
        c['throughput_change_pct']=(1/c['time_ratio']-1)*100
        c['verdict']='development' if m['spec']['stage']!='confirmation' else 'uncertain'
        if m['spec']['stage']=='confirmation' and c['n']>=12 and c['p_holm']<.05:
            if c['ci95'][1]<1 and c['mechanism_active_pairs']:c['verdict']='faster'
            elif c['ci95'][0]>1:c['verdict']='slower'
    dump(root/'summary.json',summary);dump(root/'comparisons.json',comparisons)
    return summary,comparisons

def activate():
    core.configuration=configuration;core.trace=trace;core.SOURCES=SOURCES;core.report=report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['spec','binary','remote-root','freeze','reference']:p.add_argument('--'+name,type=Path)
    args=p.parse_args();activate()
    if args.operation=='run':core.run(args)
    elif args.operation=='report':report(args.output)
    else:
        r=core.audit(args.output);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
