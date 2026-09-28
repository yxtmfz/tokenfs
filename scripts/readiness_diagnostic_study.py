#!/usr/bin/env python3
"""Two fixed diagnostic replays of the prior failing seed, with no policy change."""
from __future__ import annotations
import argparse,json,math,random,shutil,statistics,time
from pathlib import Path
from evidence_benchmark import MIB,dump,run_case,sha
from measured_study import check_mount,digest
import request_cost_study as previous
from tail_diagnostic_analysis import analyze_case
VARIANTS=['AdaptiveHP','PoolSIEVE1']
SOURCES=previous.SOURCES+['src/copy_cost.h','scripts/readiness_diagnostic_study.py',
 'scripts/tail_diagnostic_analysis.py','docs/inflight-shared-read-plan.md']

def configuration(name,case,remote,quota,direct):
    cfg=previous.configuration(name,case,remote,quota,direct)
    cfg['policy']['request_trace_path']=str(case/'request-trace.json')
    return cfg

def expected_spec(stage='diagnostic'):
    if stage!='diagnostic':raise ValueError('diagnostic only')
    return dict(stage=stage,blocks=[dict(id='moving_shared-3241',scenario='moving_shared',
      seed=3241,variants=VARIANTS,quota_mib=24,shard_mib=2,requests=576)])

def validate_spec(spec):
    if spec!=expected_spec():raise ValueError('fixed two-run diagnostic replay mismatch')

def trace(block):return previous.trace(block)
def arm_order(block):return VARIANTS.copy()

def run(args):
    root=args.output.resolve();remote=args.remote_root.resolve();binary=args.binary.resolve()
    repo=Path(__file__).resolve().parents[1];spec=json.loads(args.spec.read_text())
    verify=False
    if spec['stage'] not in ['diagnostic']:raise ValueError('stage')
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
    result={}
    for name in VARIANTS:
        case=root/'moving_shared-3241'/name
        result[name]=analyze_case(case)
    dump(root/'diagnostics.json',result)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['spec','binary','remote-root','freeze']:p.add_argument('--'+name,type=Path)
    args=p.parse_args()
    if args.operation=='run':run(args)
    elif args.operation=='report':report(args.output)
    else:
        review=audit(args.output);print(json.dumps(review));raise SystemExit(0 if review['passed'] else 1)
