#!/usr/bin/env python3
"""Small, separately labeled logical-domain speed supplement; no physical-GPU claim."""
from __future__ import annotations
import argparse
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
from evidence_benchmark import MIB,dump,run_case,sha
from evidence_report import interval
from measured_study import check_mount,configuration,digest


def trace(block):
    if block['scenario'] not in ['domain_stable','domain_shift']:raise ValueError('unknown logical-domain scenario')
    rng=random.Random(block['seed']);events=[]
    for i in range(block['requests']):
        phase=i*4//block['requests'] if block['scenario']=='domain_shift' else 0
        key=phase*8+rng.randrange(4) if rng.random()<.85 else rng.randrange(32,64)
        events.append(dict(index=i,key=key,caller=i%3,bytes=block['shard_mib']*MIB))
    return events


def run(args):
    root=args.output.resolve();remote=args.remote_root.resolve();binary=args.binary.resolve()
    reference=json.loads(args.reference.read_text());spec=json.loads(args.spec.read_text())
    completed=json.loads((args.reference.parent/'batch-audit.json').read_text())
    if not reference['verify'] or not completed['passed'] or completed['checked_runs']!=completed['expected_runs']:raise ValueError('content-validation reference is incomplete or failed')
    if reference['build_type']!='Release' or sha(binary)!=reference['binary_sha256']:raise ValueError('unvalidated binary')
    source=Path(__file__).resolve().parents[1]
    for name,expected in reference['source_hashes'].items():
        if sha(source/name)!=expected:raise ValueError('runtime differs from content-validation reference: '+name)
    identity=check_mount(remote,False)
    root.mkdir(parents=True,exist_ok=False);data_root=remote/('domain-'+root.name);data_root.mkdir(exist_ok=False)
    dump(root/'manifest.json',dict(spec=spec,spec_sha256=digest(spec),stage='descriptive-supplement',
        binary_sha256=sha(binary),script_sha256=sha(Path(__file__)),source_hashes=reference['source_hashes'],
        reference_sha256=sha(args.reference),output=str(root),remote_data=str(data_root),**identity))
    for b in spec['blocks']:
        block=root/b['id'];block.mkdir();data=data_root/b['id'];(data/'gpu0').mkdir(parents=True)
        expected={}
        for key in range(64):
            path=data/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(b['seed']*100000+key).randbytes(MIB)
            with path.open('wb') as f:
                for _ in range(b['shard_mib']):f.write(payload)
                f.flush();os.fsync(f.fileno())
            expected[str(key)]=sha(path)
        events=trace(b);order=b['variants'].copy();random.Random(b['seed']).shuffle(order)
        dump(block/'trace.json',events);dump(block/'objects.json',expected)
        dump(block/'input.json',dict(spec=b,trace_sha256=digest(events),objects_sha256=digest(expected),order=order))
        for name in order:
            case=block/name;cfg=configuration(name,case,data,b['quota_mib'],True)
            result=run_case(binary,case,data,name,events,expected,b['quota_mib'],False,True,configuration=cfg)
            print(json.dumps(dict(block=b['id'],strategy=name,mib_s=result['effective_mib_s'],wall_s=result['job_wall_s'])),flush=True)
        shutil.rmtree(data)
    if not audit(root)['passed']:raise RuntimeError('domain supplement audit failed')


def audit(root):
    m=json.loads((root/'manifest.json').read_text());errors=[];checked=0;seen=set()
    if digest(m['spec'])!=m['spec_sha256']:errors.append('changed specification')
    for b in m['spec']['blocks']:
        block=root/b['id'];events=trace(b);order=b['variants'].copy();random.Random(b['seed']).shuffle(order)
        if not (block/'input.json').exists():errors.append(b['id']+': missing input');continue
        frozen=json.loads((block/'input.json').read_text());expected=json.loads((block/'objects.json').read_text())
        if frozen!=dict(spec=b,trace_sha256=digest(events),objects_sha256=digest(expected),order=order) or json.loads((block/'trace.json').read_text())!=events:errors.append(b['id']+': changed input')
        for name in order:
            seen.add((b['id'],name));case=block/name
            if not (case/'result.json').exists():errors.append(f'{b["id"]}/{name}: missing result');continue
            r=json.loads((case/'result.json').read_text());rows=json.loads((case/'requests.json').read_text());metrics=r['metrics']
            cfg=configuration(name,Path(m['output'])/b['id']/name,Path(m['remote_data'])/b['id'],b['quota_mib'],True)
            total=sum(e['bytes'] for e in events)
            checks=[json.loads((case/'config.json').read_text())==cfg,r['status']=='ok',r['strategy']==name,not r['verify_every_request'],
                len(rows)==len(events) and all(all(row.get(k)==v for k,v in e.items()) for row,e in zip(rows,events)),
                r['logical_bytes']==total,metrics.get('read_bytes',0)==total,metrics.get('read_open_count',0)==len(events),
                metrics.get('read_local_bytes',0)+metrics.get('read_remote_bytes',0)==total,
                all(metrics.get(f'qos_gpu{g}_read_bytes',0)==sum(e['bytes'] for e in events if e['caller']==g) for g in range(3)),
                metrics.get('background_submitted',0)==metrics.get('background_completed',0),
                not any(v for k,v in metrics.items() if k.endswith('error_count')),
                max(r['retained_cache_bytes'])<=b['quota_mib']*MIB,
                math.isfinite(r['job_wall_s']) and r['job_wall_s']>0,
                abs(r['effective_mib_s']-total/MIB/r['job_wall_s'])<1e-8]
            if not all(checks):errors.append(f'{b["id"]}/{name}: failed checks {checks}')
            checked+=1
    actual={(p.parent.parent.name,p.parent.name) for p in root.glob('*/*/result.json')}
    if actual-seen:errors.append('unexpected case')
    if list(root.rglob('failure.json')):errors.append('failed case present')
    answer=dict(passed=not errors,checked_runs=checked,expected_runs=sum(len(b['variants']) for b in m['spec']['blocks']),errors=errors)
    dump(root/'batch-audit.json',answer);return answer


def report(root):
    if not audit(root)['passed']:raise RuntimeError('audit failed')
    m=json.loads((root/'manifest.json').read_text());summary=[]
    for scene in ['domain_stable','domain_shift']:
        pairs=[]
        for b in m['spec']['blocks']:
            if b['scenario']==scene:
                pairs.append(tuple(json.loads((root/b['id']/name/'result.json').read_text()) for name in ['AURA-adaptive','RecentLFU-admit']))
        logs=[math.log(a['job_wall_s']/r['job_wall_s']) for a,r in pairs]
        summary.append(dict(scenario=scene,n=len(pairs),aura_mib_s=statistics.mean(a['effective_mib_s'] for a,r in pairs),reference_mib_s=statistics.mean(r['effective_mib_s'] for a,r in pairs),
            time_ratio=math.exp(statistics.mean(logs)),ci95=interval(logs,math.exp),
            with_drain_ratio=math.exp(statistics.mean(math.log(a['completed_with_background_s']/r['completed_with_background_s']) for a,r in pairs)),
            verdict='descriptive n=3; three logical callers share one host/disk; not physical multi-GPU or original-trace concurrency'))
    dump(root/'summary.json',summary);return summary


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['binary','reference','spec','remote-root']:p.add_argument('--'+name,type=Path)
    args=p.parse_args()
    if args.operation=='run':run(args)
    elif args.operation=='audit':
        result=audit(args.output);print(json.dumps(result));raise SystemExit(0 if result['passed'] else 1)
    else:print(json.dumps(report(args.output),indent=2))
