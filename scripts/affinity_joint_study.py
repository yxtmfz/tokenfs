#!/usr/bin/env python3
"""Actual FUSE/NVMe-TCP experiment for private logical cache domains.

No injected delays, GPU inference or physical-node locality claim. Development,
content checks and held-out confirmation are separate immutable directories.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import time

from evidence_benchmark import MIB, config_for, dump, run_case, sha
from evidence_report import interval, paired_p, holm
from measured_study import check_mount, digest

VARIANTS=['RemoteOnly','LRU','LFU','RecentLFU','B','H','P','I','J','J-no-H','J-no-P']
SCENES=['static_affinity','caller_shift','hot_shift','coupled','public_toolagent','uniform']
SOURCES=['src/main.cpp','src/measured_policy.h','scripts/affinity_joint_study.py',
         'scripts/evidence_benchmark.py','scripts/evidence_report.py','scripts/evidence_audit.py',
         'scripts/measured_study.py']


def configuration(name,case,remote,quota,direct):
    cfg=config_for({'LRU':'LRU-equal','LFU':'LFU-equal','RemoteOnly':'RemoteOnly'}.get(name,'AURA-core'),case,remote,quota,direct)
    p=cfg['policy']
    p.update(private_cache_domains=True,measured_track_affinity=True,measured_affinity_window=128,
             measured_shift_reset=False,measured_window=128,measured_aging=True,
             measured_affinity_gate=False,measured_joint_admission=True)
    if name in ['B','H','P','I','J','J-no-H','J-no-P','RecentLFU']:
        p.update(measured_policy=True,measured_admission=True,measured_cost=True,
                 measured_value_victim=True,measured_size_aware=True,measured_frequency_admission=False,
                 measured_joint_admission=name in ['J','J-no-H','J-no-P','RecentLFU'],
                 measured_shift_reset=name in ['H','I','J','J-no-P'],
                 measured_affinity_gate=name in ['P','I','J','J-no-H'])
        if name=='RecentLFU':p.update(measured_cost=False,measured_size_aware=False,measured_frequency_admission=True)
    return cfg


def synthetic(block):
    rng=random.Random(block['seed']);events=[];n=block['requests'];scene=block['scenario']
    for i in range(n):
        phase=min(3,i*4//n);caller=i%3
        if scene=='static_affinity':
            key=caller*4+rng.randrange(4) if rng.random()<.8 else rng.randrange(12)
        elif scene=='caller_shift':
            caller=phase%3 if rng.random()<.85 else rng.randrange(3)
            key=rng.randrange(4) if rng.random()<.85 else rng.randrange(32,64)
        elif scene=='hot_shift':
            key=phase*12+caller*4+rng.randrange(4) if rng.random()<.85 else rng.randrange(48,64)
        elif scene=='coupled':
            caller=phase%3 if rng.random()<.85 else rng.randrange(3)
            key=phase*8+rng.randrange(8) if rng.random()<.85 else rng.randrange(32,64)
        elif scene=='uniform':
            caller=rng.randrange(3);key=rng.randrange(64)
        else:raise ValueError(scene)
        events.append(dict(index=i,key=key,caller=caller,bytes=block['shard_mib']*MIB))
    return events


def trace(block):
    return block['events'] if block['scenario']=='public_toolagent' else synthetic(block)


def run(args):
    root=args.output.resolve();remote=args.remote_root.resolve();binary=args.binary.resolve()
    repo=Path(__file__).resolve().parents[1];spec=json.loads(args.spec.read_text())
    verify=spec['stage']=='correctness'
    if spec['stage'] not in ['correctness','development','confirmation']:raise ValueError('stage')
    if 'CMAKE_BUILD_TYPE:STRING=Release' not in (binary.parent/'CMakeCache.txt').read_text():raise ValueError('Release required')
    hashes={p:sha(repo/p) for p in SOURCES};identity=check_mount(remote,verify)
    if spec['stage']=='confirmation':
        if not args.freeze:raise ValueError('confirmation requires frozen source/build/spec')
        frozen=json.loads(args.freeze.read_text())
        if frozen['source_hashes']!=hashes or frozen['binary_sha256']!=sha(binary) or frozen['spec_sha256']!=sha(args.spec):raise ValueError('freeze mismatch')
        verified_variants=set()
        for ref_path in [args.reference]+[Path(x) for x in frozen['additional_correctness_references']]:
            reference=json.loads(ref_path.read_text())
            if not reference['passed'] or reference['checked_runs']!=reference['expected_runs']:raise ValueError('correctness reference incomplete')
            reference_manifest=json.loads((ref_path.parent/'manifest.json').read_text())
            if not reference_manifest['verify'] or reference_manifest['binary_sha256']!=sha(binary):raise ValueError('unvalidated runtime binary')
            if any(reference_manifest['source_hashes'][p]!=hashes[p] for p in ['src/main.cpp','src/measured_policy.h','scripts/evidence_benchmark.py']):raise ValueError('runtime differs from content verification')
            verified_variants.update(n for b in reference_manifest['spec']['blocks'] for n in b['variants'])
        if not {n for b in spec['blocks'] for n in b['variants']}<=verified_variants:raise ValueError('unvalidated strategy')
    root.mkdir(parents=True,exist_ok=False);data_root=remote/('aj-'+root.name);data_root.mkdir(exist_ok=False)
    manifest=dict(spec=spec,spec_sha256=digest(spec),source_hashes=hashes,binary_sha256=sha(binary),
        output=str(root),remote_data=str(data_root),verify=verify,backend_direct=True,
        topology='three private logical domains on the same cn7 disk; only caller-local or NVMe/TCP canonical; serialized callers',
        created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**identity)
    dump(root/'manifest.json',manifest)
    for b in spec['blocks']:
        block=root/b['id'];block.mkdir();data=data_root/b['id'];(data/'gpu0').mkdir(parents=True)
        events=trace(b);expected={}
        for key in sorted({e['key'] for e in events}):
            path=data/'gpu0'/f'shard-{key:06d}.tokens'
            payload=random.Random(b['seed']*100000+key).randbytes(MIB)
            with path.open('wb') as f:
                for _ in range(b['shard_mib']):f.write(payload)
                f.flush()
                import os
                os.fsync(f.fileno())
            expected[str(key)]=sha(path)
        order=b['variants'].copy();random.Random(b['seed']).shuffle(order)
        dump(block/'trace.json',events);dump(block/'objects.json',expected)
        dump(block/'input.json',dict(spec=b,order=order,trace_sha256=digest(events),objects_sha256=digest(expected)))
        for name in order:
            case=block/name;cfg=configuration(name,case,data,b['quota_mib'],True)
            result=run_case(binary,case,data,name,events,expected,b['quota_mib'],verify,True,configuration=cfg)
            print(json.dumps(dict(block=b['id'],strategy=name,mib_s=result['effective_mib_s'],wall_s=result['job_wall_s'],
                resets=result['metrics'].get('measured_shift_resets',0),affinity_rejects=result['metrics'].get('measured_precheck_affinity',0),
                joint_rejects=result['metrics'].get('measured_precheck_victim_loss',0))),flush=True)
        shutil.rmtree(data)
    if not audit(root)['passed']:raise RuntimeError('batch audit failed')
    if not verify:report(root)


def audit(root):
    m=json.loads((root/'manifest.json').read_text());errors=[];checked=0;seen=set()
    if digest(m['spec'])!=m['spec_sha256']:errors.append('spec changed')
    for b in m['spec']['blocks']:
        block=root/b['id'];events=trace(b);order=b['variants'].copy();random.Random(b['seed']).shuffle(order)
        if not (block/'input.json').exists():errors.append(b['id']+':missing block');continue
        expected=json.loads((block/'objects.json').read_text())
        if json.loads((block/'input.json').read_text())!=dict(spec=b,order=order,trace_sha256=digest(events),objects_sha256=digest(expected)) or json.loads((block/'trace.json').read_text())!=events:errors.append(b['id']+':input changed')
        for name in order:
            seen.add((b['id'],name));case=block/name
            if not (case/'result.json').exists():errors.append(str(case)+':missing result');continue
            r=json.loads((case/'result.json').read_text());rows=json.loads((case/'requests.json').read_text());metrics=r['metrics']
            total=sum(e['bytes'] for e in events)
            cfg=configuration(name,Path(m['output'])/b['id']/name,Path(m['remote_data'])/b['id'],b['quota_mib'],True)
            checks=[json.loads((case/'config.json').read_text())==cfg,r['strategy']==name,r['status']=='ok',r['verify_every_request']==m['verify'],
                len(events)==len(rows),all(all(row.get(k)==v for k,v in e.items()) for row,e in zip(rows,events)),
                total==r['logical_bytes']==metrics.get('read_bytes',0),len(events)==metrics.get('read_open_count',0),
                total==metrics.get('read_local_bytes',0)+metrics.get('read_remote_bytes',0),
                metrics.get('private_domain_read_count',0)==sum(e['caller']!=0 for e in events),
                all(metrics.get(f'qos_gpu{g}_read_bytes',0)==sum(e['bytes'] for e in events if e['caller']==g) for g in range(3)),
                metrics.get('background_submitted',0)==metrics.get('background_completed',0),
                not any(v for k,v in metrics.items() if k.endswith('error_count')),
                max(r['retained_cache_bytes'])<=(0 if name=='RemoteOnly' else b['quota_mib']*MIB),
                all(isinstance(r[k],(int,float)) and math.isfinite(r[k]) and r[k]>=0 for k in ['job_wall_s','effective_mib_s','completed_with_background_s','daemon_cpu_s','daemon_peak_rss_kib','request_p50_s','request_p99_s']),
                r['job_wall_s']>0,r['completed_with_background_s']>=r['job_wall_s'],
                abs(r['effective_mib_s']-total/MIB/r['job_wall_s'])<1e-8]
            previous=0
            for row in rows:
                checks.append(previous<=row['issued_s']<=row['completed_s']<=r['job_wall_s'])
                checks.append(0<=row['seconds']<=row['completed_s']-row['issued_s']+1e-6)
                previous=row['completed_s']
                if m['verify']:checks.append(row['sha256']==expected[str(row['key'])])
            if not all(checks):errors.append(f"{b['id']}/{name}: failed { [i for i,v in enumerate(checks) if not v] }")
            checked+=1
    actual={(p.parent.parent.name,p.parent.name) for p in root.glob('*/*/result.json')}
    if actual-seen:errors.append('unexpected case')
    if list(root.rglob('failure.json')):errors.append('failed attempt present')
    answer=dict(passed=not errors,checked_runs=checked,expected_runs=sum(len(b['variants']) for b in m['spec']['blocks']),errors=errors)
    dump(root/'batch-audit.json',answer);return answer


def report(root):
    if not audit(root)['passed']:raise RuntimeError('incomplete batch')
    m=json.loads((root/'manifest.json').read_text())
    if m['verify']:raise ValueError('correctness is not speed evidence')
    all_results={(p.parent.parent.name,p.parent.name):json.loads(p.read_text()) for p in root.glob('*/*/result.json')}
    summary=[];comparisons=[];interactions=[];activity=[]
    pairings=[('factorial_hotspot','H','B'),('factorial_hotspot','I','P'),('factorial_affinity','P','B'),('factorial_affinity','I','H'),
              ('hotspot','J','J-no-H'),('affinity','J','J-no-P'),
              ('joint','J','I')]+[('overall','J',base) for base in ['RemoteOnly','LRU','LFU','RecentLFU']]
    for scene in sorted({b['scenario'] for b in m['spec']['blocks']}):
        blocks=[b for b in m['spec']['blocks'] if b['scenario']==scene]
        for name in VARIANTS:
            rs=[all_results[b['id'],name] for b in blocks if name in b['variants']]
            if not rs:continue
            summary.append(dict(scenario=scene,strategy=name,n=len(rs),mean_mib_s=statistics.mean(r['effective_mib_s'] for r in rs),
                mean_wall_s=statistics.mean(r['job_wall_s'] for r in rs),mean_copy_mib=statistics.mean(sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB for r in rs),
                mean_p99_ms=statistics.mean(r['request_p99_s']*1000 for r in rs),mean_cpu_s=statistics.mean(r['daemon_cpu_s'] for r in rs)))
        for family,treatment,baseline in pairings:
            pairs=[(all_results[b['id'],treatment],all_results[b['id'],baseline]) for b in blocks if treatment in b['variants'] and baseline in b['variants']]
            if not pairs:continue
            logs=[math.log(a['job_wall_s']/b['job_wall_s']) for a,b in pairs]
            comparisons.append(dict(scenario=scene,family=family,treatment=treatment,baseline=baseline,n=len(pairs),
                time_ratio=math.exp(statistics.mean(logs)),ci95=interval(logs,math.exp),p_raw=paired_p(logs),p_holm=None,
                treatment_mib_s=statistics.mean(a['effective_mib_s'] for a,b in pairs),baseline_mib_s=statistics.mean(b['effective_mib_s'] for a,b in pairs),
                with_drain_ratio=math.exp(statistics.mean(math.log(a['completed_with_background_s']/b['completed_with_background_s']) for a,b in pairs))))
        iv=[all_results[b['id'],'I']['job_wall_s']-all_results[b['id'],'H']['job_wall_s']-all_results[b['id'],'P']['job_wall_s']+all_results[b['id'],'B']['job_wall_s'] for b in blocks if all(n in b['variants'] for n in ['I','H','P','B'])]
        if iv:interactions.append(dict(scenario=scene,n=len(iv),mean_interaction_s=statistics.mean(iv),ci95=interval(iv),definition='T(I)-T(H)-T(P)+T(B); negative favors interaction; exploratory'))
    for family in {r['family'] for r in comparisons}:holm([r for r in comparisons if r['family']==family])
    for row in comparisons:
        row['throughput_change_pct']=(1/row['time_ratio']-1)*100
        row['verdict']='development' if m['spec']['stage']!='confirmation' else 'uncertain'
        if m['spec']['stage']=='confirmation' and row['n']>=12 and row['p_holm']<.05:
            if row['ci95'][1]<1:row['verdict']='faster'
            if row['ci95'][0]>1:row['verdict']='slower'
        row['mechanism_active_pairs']=None;row['different_action_pairs']=None
        if row['family'] in ['hotspot','affinity','joint']:
            active=0;different=0
            for b in m['spec']['blocks']:
                if b['scenario']!=row['scenario'] or not {row['treatment'],row['baseline']}<=set(b['variants']):continue
                mm=all_results[b['id'],row['treatment']]['metrics']
                active+=bool({'hotspot':mm.get('measured_shift_resets',0),
                    'affinity':mm.get('measured_precheck_affinity',0)+mm.get('measured_commit_affinity',0),
                    'joint':mm.get('measured_precheck_victim_loss',0)+mm.get('measured_commit_victim_loss',0)}[row['family']])
                def actions(name):
                    events=json.loads((root/b['id']/name/'policy-events.json').read_text())
                    return [(e['action'],e['logical_path'],e['gpu_id']) for e in events if e['action'] in ['EVICT','PROMOTE_READY','REPLICATE_READY']]
                different+=actions(row['treatment'])!=actions(row['baseline'])
            row['mechanism_active_pairs']=active;row['different_action_pairs']=different
            row['attribution']='mechanism activity observed; inspect speed verdict' if active else 'target mechanism unobserved; no component benefit claim'
    for (block,name),r in all_results.items():
        mm=r['metrics'];activity.append(dict(block=block,strategy=name,shift_resets=mm.get('measured_shift_resets',0),
            affinity_precheck=mm.get('measured_precheck_affinity',0),affinity_commit=mm.get('measured_commit_affinity',0),
            victim_loss_precheck=mm.get('measured_precheck_victim_loss',0),victim_loss_commit=mm.get('measured_commit_victim_loss',0),
            local_bytes=mm.get('read_local_bytes',0),remote_bytes=mm.get('read_remote_bytes',0)))
    for name,value in [('summary',summary),('comparisons',comparisons),('interactions',interactions),('activity',activity)]:dump(root/(name+'.json'),value)
    return summary,comparisons


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['spec','binary','remote-root','freeze','reference']:p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.operation=='run':run(a)
    elif a.operation=='report':report(a.output)
    else:
        result=audit(a.output);print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
