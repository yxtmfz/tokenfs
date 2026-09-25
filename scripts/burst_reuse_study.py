#!/usr/bin/env python3
"""Bounded burst-reuse experiment with both pooled SIEVE admission rules."""
from __future__ import annotations
import argparse,json,math,random,shutil,statistics,time
from pathlib import Path
from evidence_benchmark import MIB,dump,run_case,sha
from measured_study import check_mount,digest
from paper_minimal_study import configuration as base_configuration
from compact_planning_study import configuration as previous_configuration, trace as moving_trace
VARIANTS=['OldHP','BurstHP','PoolSIEVE2','PoolSIEVE1']
SOURCES=['src/main.cpp','src/measured_policy.h','src/sieve_policy.h',
 'scripts/burst_reuse_study.py','scripts/compact_planning_study.py',
 'scripts/affinity_joint_study.py','scripts/paper_minimal_study.py',
 'scripts/evidence_benchmark.py','scripts/evidence_report.py','scripts/measured_study.py',
 'tests/measured_policy_test.cpp','tests/policy_metadata_test.cpp',
 'tests/burst_reuse_test.py','docs/burst-reuse-sieve-plan.md','CMakeLists.txt']

def configuration(name,case,remote,quota,direct):
    if name not in VARIANTS:raise ValueError(name)
    cfg=previous_configuration('PoolSIEVE2' if name.startswith('PoolSIEVE') else 'HP',case,remote,quota,direct)
    cfg['policy']['measured_burst_reuse']=name=='BurstHP'
    if name=='PoolSIEVE1':cfg['policy']['read_through_min_reads']=1
    return cfg

def expected_spec(stage):
    if stage not in ['development','correctness']:raise ValueError('stage')
    speed=stage=='development';blocks=[]
    for scene,seeds,arms in [('moving_shared',[3101,3102,3103] if speed else [3099],VARIANTS),
                            ('uniform',[3111,3112] if speed else [3098],VARIANTS[1:])]:
        for seed in seeds:blocks.append(dict(id=f'{scene}-{seed}',scenario=scene,seed=seed,variants=arms,quota_mib=24,shard_mib=2,requests=576 if speed else 96))
    return dict(stage=stage,blocks=blocks)

def validate_spec(spec):
    if spec!=expected_spec(spec['stage']):raise ValueError('frozen matrix mismatch')

def trace(block):
    if block['scenario']=='moving_shared':return moving_trace(block)
    if block['scenario']!='uniform':raise ValueError('scenario')
    rng=random.Random(block['seed'])
    return [dict(index=i,key=rng.randrange(24),caller=rng.randrange(3),bytes=block['shard_mib']*MIB) for i in range(block['requests'])]

def arm_order(block):
    order=block['variants'].copy();random.Random(3100).shuffle(order)
    offset=(block['seed']%100)%len(order)
    return order[offset:]+order[:offset]


def run(args):
    root=args.output.resolve();remote=args.remote_root.resolve();binary=args.binary.resolve()
    repo=Path(__file__).resolve().parents[1];spec=json.loads(args.spec.read_text())
    verify=spec['stage']=='correctness'
    if spec['stage'] not in ['correctness','development']:raise ValueError('stage')
    if 'CMAKE_BUILD_TYPE:STRING=Release' not in (binary.parent/'CMakeCache.txt').read_text():raise ValueError('Release required')
    hashes={p:sha(repo/p) for p in SOURCES};identity=check_mount(remote,verify)
    frozen=json.loads(args.freeze.read_text())
    if frozen['source_hashes']!=hashes or frozen['binary_sha256']!=sha(binary) or frozen['specs'][spec['stage']]!=sha(args.spec):
        raise ValueError('pilot freeze mismatch')
    validate_spec(spec)
    root.mkdir(parents=True,exist_ok=False);data_root=remote/('aj-'+root.name);data_root.mkdir(exist_ok=False)
    manifest=dict(spec=spec,spec_sha256=digest(spec),source_hashes=hashes,binary_sha256=sha(binary),
        output=str(root),remote_data=str(data_root),verify=verify,backend_direct=True,
        topology='three logical cache partitions on one shared host disk; access policy varied explicitly; serialized callers; no physical GPUs',
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
        order=arm_order(b)
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
    validate_spec(m['spec'])
    if digest(m['spec'])!=m['spec_sha256']:errors.append('spec changed')
    for b in m['spec']['blocks']:
        block=root/b['id'];events=trace(b);order=arm_order(b)
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
                0<=metrics.get('peer_cache_read_bytes',0)<=metrics.get('read_local_bytes',0),
                all(v<=g['local_quota_mib']*MIB for v,g in zip(r['retained_cache_bytes'],cfg['gpus'])),
                sum(g['local_quota_mib'] for g in cfg['gpus'])==24,
                total==r['logical_bytes']==metrics.get('read_bytes',0),len(events)==metrics.get('read_open_count',0),
                total==metrics.get('read_local_bytes',0)+metrics.get('read_remote_bytes',0),
                metrics.get('private_domain_read_count',0)==(sum(e['caller']!=0 for e in events) if cfg['policy']['private_cache_domains'] else 0),
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
    a=audit(root)
    if not a['passed']:raise ValueError(a)
    m=json.loads((root/'manifest.json').read_text())
    if m['verify']:return
    rows=[];pairs=[]
    for scene in ['moving_shared','uniform']:
        blocks=[b for b in m['spec']['blocks'] if b['scenario']==scene]
        rs={(b['id'],n):json.loads((root/b['id']/n/'result.json').read_text()) for b in blocks for n in b['variants']}
        for name in blocks[0]['variants']:
            vals=[rs[b['id'],name] for b in blocks]
            fns=dict(mib_s=lambda r:r['effective_mib_s'],wall_s=lambda r:r['job_wall_s'],cpu_s=lambda r:r['daemon_cpu_s'],p99_ms=lambda r:r['request_p99_s']*1000,remote_mib=lambda r:r['metrics'].get('read_remote_bytes',0)/MIB,copy_mib=lambda r:sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB,first_read_selections=lambda r:r['metrics'].get('shared_burst_first_read_selected',0),forecast_plans=lambda r:r['metrics'].get('measured_burst_forecast_plans',0))
            rows.append(dict(scenario=scene,strategy=name,n=len(vals),**{k:statistics.mean(f(r) for r in vals) for k,f in fns.items()}))
        for baseline in [n for n in blocks[0]['variants'] if n!='BurstHP']:
            per=[]
            for b in blocks:
                x=rs[b['id'],'BurstHP'];y=rs[b['id'],baseline]
                per.append(dict(seed=b['seed'],gain_pct=(y['job_wall_s']/x['job_wall_s']-1)*100,drain_gain_pct=(y['completed_with_background_s']/x['completed_with_background_s']-1)*100,p99_change_pct=(x['request_p99_s']/y['request_p99_s']-1)*100))
            gain=(math.exp(statistics.mean(math.log1p(p['gain_pct']/100) for p in per))-1)*100
            pairs.append(dict(scenario=scene,treatment='BurstHP',baseline=baseline,n=len(per),paired_gain_pct=gain,wins=sum(p['gain_pct']>0 for p in per),per_seed=per,pilot_speed_gate=gain>=5 and all(p['gain_pct']>0 for p in per)))
    dump(root/'summary.json',rows);dump(root/'comparisons.json',pairs)
    print(json.dumps(pairs),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['spec','binary','remote-root','freeze']:p.add_argument('--'+name,type=Path)
    args=p.parse_args()
    if args.operation=='run':run(args)
    elif args.operation=='report':report(args.output)
    else:
        review=audit(args.output);print(json.dumps(review));raise SystemExit(0 if review['passed'] else 1)
