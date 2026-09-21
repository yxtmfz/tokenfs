#!/usr/bin/env python3
"""Small, fixed storage-only H/J closeout; no affinity tuning or GPU claims."""
from __future__ import annotations
import argparse,json,math,statistics
from pathlib import Path
import affinity_joint_study as core
from evidence_benchmark import dump
from evidence_report import interval,paired_p,holm

SCENES=['static_affinity','hot_shift','public_toolagent','uniform']
MAIN=['RemoteOnly','LRU','SIEVE','SIEVE-2hit','RecentLFU','Full']
VARIANTS=MAIN+['no-H','no-J','no-HJ']
SOURCES=core.SOURCES+['src/sieve_policy.h','scripts/paper_minimal_study.py']
base_configuration=core.configuration

def configuration(name,case,remote,quota,direct):
    if name not in VARIANTS:raise ValueError(name)
    mapped={'Full':'J-no-P','no-H':'J-no-H','no-J':'H','no-HJ':'B','SIEVE':'LRU','SIEVE-2hit':'LRU'}.get(name,name)
    cfg=base_configuration(mapped,case,remote,quota,direct);p=cfg['policy']
    p.update(measured_track_affinity=False,measured_affinity_gate=False,
             measured_affinity_recent_demand=False,measured_affinity_handover_epoch=False,
             affinity_placement=False)
    # Standard demand-on-miss LRU/SIEVE have no compulsory second-hit filter.
    # Also retain SIEVE plus the common two-hit filter to isolate admission cost.
    if name in ['LRU','SIEVE','SIEVE-2hit']:
        p['read_through_min_reads']=2 if name=='SIEVE-2hit' else 1
        if name.startswith('SIEVE'):p['local_eviction_policy']='sieve'
    return cfg

def report(root):
    activate();a=core.audit(root)
    if not a['passed']:raise ValueError(a)
    m=json.loads((root/'manifest.json').read_text())
    if m['verify']:raise ValueError('content checks are not speed evidence')
    rs={(p.parent.parent.name,p.parent.name):json.loads(p.read_text()) for p in root.glob('*/*/result.json')}
    summary=[];comparisons=[];interactions=[]
    groups=sorted({b.get('condition',b['scenario']) for b in m['spec']['blocks']})
    pairings=[('overall','Full',x) for x in ['LRU','SIEVE','SIEVE-2hit','RecentLFU']]
    pairings += [('remote_reference','Full','RemoteOnly'),('mechanism','Full','no-H'),('mechanism','Full','no-J')]
    for scene in groups:
        blocks=[b for b in m['spec']['blocks'] if b.get('condition',b['scenario'])==scene]
        for name in VARIANTS:
            values=[rs[b['id'],name] for b in blocks if name in b['variants']]
            if not values:continue
            summary.append(dict(scenario=scene,strategy=name,n=len(values),
                mib_s=statistics.mean(r['effective_mib_s'] for r in values),
                wall_s=statistics.mean(r['job_wall_s'] for r in values),
                with_drain_s=statistics.mean(r['completed_with_background_s'] for r in values),
                cpu_s=statistics.mean(r['daemon_cpu_s'] for r in values),
                rss_kib=statistics.mean(r['daemon_peak_rss_kib'] for r in values),
                p99_ms=statistics.mean(r['request_p99_s']*1000 for r in values),
                remote_mib=statistics.mean(r['metrics'].get('read_remote_bytes',0)/1048576 for r in values),
                copy_mib=statistics.mean(sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/1048576 for r in values),
                shift_resets=statistics.mean(r['metrics'].get('measured_shift_resets',0) for r in values),
                joint_rejects=statistics.mean(sum(r['metrics'].get(k,0) for k in ['measured_precheck_victim_loss','measured_commit_victim_loss']) for r in values),
                sieve_evictions=statistics.mean(r['metrics'].get('evict_policy_sieve',0) for r in values)))
        for family,treatment,baseline in pairings:
            paired=[b for b in blocks if {treatment,baseline}<=set(b['variants'])]
            if not paired:continue
            values=[(rs[b['id'],treatment],rs[b['id'],baseline]) for b in paired]
            logs=[math.log(x['job_wall_s']/y['job_wall_s']) for x,y in values]
            active=None;different=None
            if family=='mechanism':
                keys=['measured_shift_resets'] if baseline=='no-H' else ['measured_precheck_victim_loss','measured_commit_victim_loss']
                active=sum(sum(x['metrics'].get(k,0) for k in keys)>0 for x,y in values)
                def actions(block,name):
                    rows=json.loads((root/block/name/'policy-events.json').read_text())
                    return [(r['action'],r['logical_path'],r['gpu_id']) for r in rows if r['action'] in ['EVICT','PROMOTE_READY','REPLICATE_READY']]
                different=sum(actions(b['id'],treatment)!=actions(b['id'],baseline) for b in paired)
            ratio=math.exp(statistics.mean(logs))
            comparisons.append(dict(scenario=scene,family=family,treatment=treatment,baseline=baseline,n=len(values),
                time_ratio=ratio,throughput_change_pct=(1/ratio-1)*100,ci95=interval(logs,math.exp),
                p_raw=paired_p(logs),p_holm=None,mechanism_active_pairs=active,different_action_pairs=different,
                with_drain_ratio=math.exp(statistics.mean(math.log(x['completed_with_background_s']/y['completed_with_background_s']) for x,y in values))))
        factorial=[rs[b['id'],'Full']['job_wall_s']-rs[b['id'],'no-H']['job_wall_s']-rs[b['id'],'no-J']['job_wall_s']+rs[b['id'],'no-HJ']['job_wall_s'] for b in blocks if {'Full','no-H','no-J','no-HJ'}<=set(b['variants'])]
        if factorial:interactions.append(dict(scenario=scene,n=len(factorial),mean_s=statistics.mean(factorial),ci95=interval(factorial),definition='T(HJ)-T(J)-T(H)+T(B); exploratory, no synergy claim'))
    for family in {c['family'] for c in comparisons}:holm([c for c in comparisons if c['family']==family])
    for c in comparisons:
        c['verdict']='descriptive' if m['spec']['stage']!='confirmation' else 'uncertain'
        if m['spec']['stage']=='confirmation' and c['n']==12 and c['p_holm']<.05:
            if c['ci95'][1]<1 and (c['family']!='mechanism' or (c['mechanism_active_pairs'] and c['different_action_pairs'])):c['verdict']='faster'
            elif c['ci95'][0]>1:c['verdict']='slower'
    for name,value in [('summary',summary),('comparisons',comparisons),('interactions',interactions)]:dump(root/(name+'.json'),value)
    return summary,comparisons

def activate():
    core.configuration=configuration;core.SOURCES=SOURCES;core.report=report

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['spec','binary','remote-root','freeze','reference']:p.add_argument('--'+name,type=Path)
    a=p.parse_args();activate()
    if a.operation=='run':core.run(a)
    elif a.operation=='report':report(a.output)
    else:
        r=core.audit(a.output);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
