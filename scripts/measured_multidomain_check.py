#!/usr/bin/env python3
"""Content/caller-accounting checks of frozen measured policies; never speed evidence."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import random

from evidence_benchmark import MIB,dump,run_case,sha
from measured_study import VARIANTS,configuration,digest


def run(args):
    binary=args.binary.resolve();root=args.output.resolve();remote=args.remote_root.resolve()
    reference=json.loads(args.reference.read_text())
    if sha(binary)!=reference['binary_sha256']:
        raise ValueError('binary differs from the completed correctness reference')
    root.mkdir(parents=True,exist_ok=False)
    data_root=remote/('multidomain-'+root.name);data_root.mkdir(exist_ok=False)
    source=Path(__file__).resolve().parents[1]
    files=['src/main.cpp','src/measured_policy.h','scripts/evidence_benchmark.py','scripts/measured_study.py']
    if any(sha(source/p)!=reference['source_hashes'][p] for p in files):
        raise ValueError('frozen runtime/driver differs from correctness reference')
    variants=[name for name in VARIANTS if name!='AURA-core']
    manifest=dict(stage='correctness',verify_every_request=True,performance_eligible=False,
        binary_sha256=sha(binary),reference_sha256=sha(args.reference),script_sha256=sha(Path(__file__)),
        runtime_source_hashes={p:sha(source/p) for p in files},seed=411,requests=96,quota_mib=2,
        scenarios=['shared_migration','shared_interleaved','shared_cycle'],variants=variants,
        cache_mode='directory backend; three logical caller IDs, same physical host')
    dump(root/'manifest.json',manifest);checked=0
    for scenario in manifest['scenarios']:
        block=root/scenario;block.mkdir();data=data_root/scenario;(data/'gpu0').mkdir(parents=True)
        expected={}
        for key in range(6):
            p=data/'gpu0'/f'shard-{key:06d}.tokens'
            with p.open('wb') as f:
                f.write(random.Random(411000+key).randbytes(MIB));f.flush();os.fsync(f.fileno())
            expected[str(key)]=sha(p)
        rng=random.Random(411);events=[]
        for i in range(96):
            caller=i//32 if scenario=='shared_migration' else i%3
            key=(i//3)%4 if scenario=='shared_cycle' else rng.randrange(6)
            events.append(dict(index=i,key=key,caller=caller,bytes=MIB))
        order=variants.copy();random.Random(411).shuffle(order)
        dump(block/'trace.json',events);dump(block/'objects.json',expected)
        dump(block/'input.json',dict(trace_sha256=digest(events),order=order))
        for name in order:
            case=block/name;cfg=configuration(name,case,data,2,False)
            result=run_case(binary,case,data,name,events,expected,2,True,False,configuration=cfg)
            metrics=result['metrics']
            checks=[result['verify_every_request'],metrics.get('read_bytes',0)==96*MIB,
                metrics.get('read_local_bytes',0)+metrics.get('read_remote_bytes',0)==96*MIB,
                all(metrics.get(f'qos_gpu{gpu}_read_bytes',0)==32*MIB for gpu in range(3)),
                metrics.get('background_submitted',0)==metrics.get('background_completed',0),
                not any(v for k,v in metrics.items() if k.endswith('error_count'))]
            if not all(checks):raise RuntimeError(f'accounting validation failed: {scenario}/{name}: {checks}')
            checked+=1;print(json.dumps(dict(scenario=scenario,strategy=name,content_verified=True,caller_bytes=[32*MIB]*3)),flush=True)
    dump(root/'batch-audit.json',dict(passed=True,checked_runs=checked,expected_runs=len(variants)*len(manifest['scenarios']),
        performance_eligible=False,checks=['per-request SHA256','retained-copy SHA256','three caller byte totals','source byte totals','queue drain','visible final quota','error counters']))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--remote-root',type=Path,required=True);args=parser.parse_args()
    try:run(args)
    except Exception as exc:
        if args.output.exists():dump(args.output/'validation-failure.json',{'error':repr(exc),'passed':False})
        raise
