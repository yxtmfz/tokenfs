#!/usr/bin/env python3
"""Observed return support; eighteen-run hotspot-focused development."""
from __future__ import annotations
import argparse,json,math,random,shutil,statistics,time
from pathlib import Path
from evidence_benchmark import MIB,dump,run_case,sha,percentile
from measured_study import check_mount,digest
from acceptance_v3 import passes
import request_cost_study as previous
VARIANTS=['Full','NoHotspot','OldFull']
SOURCES=list(dict.fromkeys(previous.SOURCES+['src/copy_cost.h','scripts/inflight_shared_study.py',
 'scripts/component_ablation_study.py','scripts/tail_diagnostic_analysis.py','tests/component_ablation_test.py',
 'docs/component-ablation-plan.md','scripts/planning_efficiency_study.py',
 'scripts/acceptance_v2.py','tests/planning_efficiency_test.py','tests/planning_equivalence_test.cpp',
 'docs/planning-efficiency-plan.md','scripts/burst_interval_study.py',
 'tests/burst_interval_test.cpp','tests/burst_interval_study_test.py','docs/burst-interval-plan.md','scripts/headroom_exploration_study.py',
 'tests/headroom_exploration_test.py','docs/headroom-exploration-plan.md','src/run_reuse.h','scripts/run_reuse_study.py','tests/run_reuse_test.cpp','tests/run_reuse_study_test.py','docs/run-reuse-plan.md','scripts/run_decay_study.py','tests/run_decay_study_test.py','docs/run-decay-plan.md','scripts/integrated_hpj_study.py','tests/integrated_hpj_study_test.py','docs/integrated-hpj-plan.md','scripts/integrated_hpj_fast_study.py','tests/integrated_hpj_fast_study_test.py','docs/integrated-hpj-fast-plan.md','scripts/integrated_hpj_novel_study.py','tests/integrated_hpj_novel_study_test.py','docs/integrated-hpj-novel-plan.md','scripts/integrated_hpj_guarded_study.py','tests/integrated_hpj_guarded_study_test.py','docs/integrated-hpj-guarded-plan.md','scripts/integrated_hpj_retained_study.py','tests/integrated_hpj_retained_test.py','docs/integrated-hpj-retained-plan.md','scripts/integrated_hpj_symmetric_study.py','tests/integrated_hpj_symmetric_test.py','docs/integrated-hpj-symmetric-plan.md','scripts/integrated_hpj_calibrated_study.py','tests/integrated_hpj_calibrated_test.py','docs/integrated-hpj-calibrated-plan.md','tests/copy_cost_test.cpp','scripts/integrated_hpj_telemetry_study.py','tests/integrated_hpj_telemetry_test.py','docs/integrated-hpj-telemetry-plan.md','scripts/integrated_hpj_readpath_study.py','tests/integrated_hpj_readpath_test.py','docs/integrated-hpj-readpath-plan.md','scripts/integrated_hpj_exactverify_study.py','tests/integrated_hpj_exactverify_test.py','docs/integrated-hpj-exactverify-plan.md','scripts/integrated_hpj_cohort_study.py','tests/integrated_hpj_cohort_test.py','docs/integrated-hpj-cohort-plan.md','scripts/integrated_hpj_cohort_writepath_study.py','tests/integrated_hpj_cohort_writepath_test.py','docs/integrated-hpj-cohort-writepath-plan.md','scripts/integrated_hpj_cohort_survival_study.py','tests/integrated_hpj_cohort_survival_test.py','docs/integrated-hpj-cohort-survival-plan.md','scripts/integrated_hpj_cohort_calibrated_study.py','tests/integrated_hpj_cohort_calibrated_test.py','docs/integrated-hpj-cohort-calibrated-plan.md','scripts/acceptance_v3.py','tests/acceptance_v3_test.py','scripts/integrated_hpj_cohort_atomic_study.py','tests/integrated_hpj_cohort_atomic_test.py','docs/integrated-hpj-cohort-atomic-plan.md','scripts/integrated_hpj_cohort_fence_study.py','tests/integrated_hpj_cohort_fence_test.py','docs/integrated-hpj-cohort-fence-plan.md','scripts/integrated_hpj_cohort_caller_study.py','tests/integrated_hpj_cohort_caller_test.py','docs/integrated-hpj-cohort-caller-plan.md','scripts/integrated_hpj_cohort_caller_independent_study.py','tests/integrated_hpj_cohort_caller_independent_test.py','docs/integrated-hpj-cohort-caller-independent-plan.md','study-configs/independent-hpj-public.json','scripts/integrated_hpj_cohort_caller_object_study.py','tests/integrated_hpj_cohort_caller_object_test.py','docs/integrated-hpj-cohort-caller-object-plan.md','scripts/integrated_hpj_cohort_caller_lazy_study.py','tests/integrated_hpj_cohort_caller_lazy_test.py','docs/integrated-hpj-cohort-caller-lazy-plan.md','scripts/integrated_hpj_cohort_caller_final_study.py','tests/integrated_hpj_cohort_caller_final_test.py','docs/integrated-hpj-cohort-caller-final-plan.md','study-configs/final-hpj-public.json','scripts/integrated_hpj_cohort_caller_support_study.py','tests/integrated_hpj_cohort_caller_support_test.py','docs/integrated-hpj-cohort-caller-support-plan.md','scripts/hotspot_freshness_correctness.py','tests/hotspot_freshness_correctness_test.py','scripts/integrated_hpj_cohort_caller_freshness_study.py','tests/integrated_hpj_cohort_caller_freshness_test.py','docs/integrated-hpj-cohort-caller-freshness-plan.md']))


def configuration(name,case,remote,quota,direct):
    if name not in VARIANTS:raise ValueError(name)
    retained=name=='OldFull'
    if retained:name='Full'
    import planning_efficiency_study as reference
    cfg=reference.configuration('PoolSIEVE1' if name=='PoolSIEVE1' else 'Full',case,remote,quota,direct)
    cfg['policy']['burst_interval_survival']=name!='PoolSIEVE1'
    cfg['policy']['reuse_scaled_exploration']=name!='PoolSIEVE1'
    cfg['policy']['persistent_run_reuse']=name!='PoolSIEVE1'
    cfg['policy']['persistent_reuse_immediate_decay']=name!='PoolSIEVE1'
    cfg['policy']['measured_static_reuse_value']=name=='NoHotspot'
    cfg['policy']['shared_caller_only']=name=='NoAffinity'
    if name=='NoJoint':cfg['policy']['measured_joint_admission']=False
    cfg['policy']['profile_control_path']=False
    cfg['policy']['batch_background_metrics']=True
    cfg['policy']['batch_policy_events']=True
    cfg['policy']['retain_read_fill']=True
    cfg['policy']['capture_local_reads']=True
    cfg['policy']['bounded_cost_warmup']=True
    cfg['policy']['novel_reuse_decay']=name!='PoolSIEVE1'
    cfg['policy']['cohort_reuse_prior']=retained
    cfg['policy']['empirical_return_support']=not retained
    cfg['policy']['recent_value_floor']=name!='PoolSIEVE1'
    return cfg


def expected_spec(stage='development'):
    if stage!='development':raise ValueError('development only')
    return dict(stage=stage,blocks=[dict(id=f'{scene}-{seed}-r{repeat}',scenario=scene,
      seed=seed,repeat=repeat,variants=VARIANTS,quota_mib=24,shard_mib=2,requests=1152)
      for repeat in [1,2] for scene,seed in [('moving_shared',74801),('public_toolagent',74802),('uniform',73702)]])


def validate_spec(spec):
    if spec!=expected_spec():raise ValueError('fixed 18-run development matrix mismatch')


def trace(block):
    if block['scenario']=='public_toolagent':
        source=json.loads((Path(__file__).resolve().parents[1]/'study-configs/final-hpj-public.json').read_text())
        return source['windows'][0]['events']
    import integrated_hpj_cohort_caller_study as retained
    return retained.trace(block)


def arm_order(block):
    order=block['variants'].copy()
    random.Random(980000+block['seed']).shuffle(order)
    return order if block['repeat']==1 else order[::-1]


def environment():
    import os
    return dict(wall_ns=time.time_ns(),monotonic_ns=time.monotonic_ns(),loadavg=list(os.getloadavg()))


def prepare(root):
    root.mkdir(parents=True,exist_ok=False)
    spec=expected_spec();validate_spec(spec)
    dump(root/'spec.json',spec)
    manifest=dict(status='prepared_not_executed',speed_runs=18,requests_per_run=1152,
                  binary_frozen=False,source_hashes={p:sha(Path(__file__).resolve().parents[1]/p) for p in SOURCES},blocks=[])
    for b in spec['blocks']:
        (root/b['id']).mkdir()
        events=trace(b);dump(root/b['id']/'trace.json',events)
        for n in b['variants']:
            (root/b['id']/n).mkdir()
            dump(root/b['id']/n/'config.json',configuration(n,Path('/PLANNED/output')/b['id']/n,Path('/PLANNED/remote')/b['id'],24,True))
        manifest['blocks'].append(dict(id=b['id'],order=arm_order(b),trace_sha256=digest(events),logical_bytes=sum(e['bytes'] for e in events)))
    dump(root/'preflight.json',manifest)

def run(args):
    root=args.output.resolve();remote=args.remote_root.resolve();binary=args.binary.resolve()
    reference=args.reference_binary.resolve()
    if sha(reference)!='b09253aa1577e6104421b797641b8952bd151c988eb3d9bef562b82d210cde37':raise ValueError('retained binary mismatch')
    repo=Path(__file__).resolve().parents[1];spec=json.loads(args.spec.read_text())
    verify=False
    if spec['stage'] not in ['development']:raise ValueError('stage')
    if 'CMAKE_BUILD_TYPE:STRING=Release' not in (binary.parent/'CMakeCache.txt').read_text():raise ValueError('Release required')
    validate_spec(spec)
    hashes={p:sha(repo/p) for p in SOURCES};identity=check_mount(remote,verify)
    frozen=json.loads(args.freeze.read_text())
    if frozen['source_hashes']!=hashes or frozen['binary_sha256']!=sha(binary) or frozen['specs'][spec['stage']]!=sha(args.spec):
        raise ValueError('pilot freeze mismatch')
    validate_spec(spec)
    root.mkdir(parents=True,exist_ok=False);data_root=remote/('aj-'+root.name);data_root.mkdir(exist_ok=False)
    manifest=dict(spec=spec,spec_sha256=digest(spec),source_hashes=hashes,binary_sha256=sha(binary),
        output=str(root),remote_data=str(data_root),verify=verify,backend_direct=True,reference_binary_sha256=sha(reference),
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
            before=environment()
            selected_binary=reference if name=='OldFull' else binary
            result=run_case(selected_binary,case,data,name,events,expected,b['quota_mib'],verify,True,configuration=cfg)
            dump(case/'execution.json',dict(binary_sha256=sha(selected_binary)))
            dump(case/'environment.json',dict(before=before,after=environment()))
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
            checks=[json.loads((case/'execution.json').read_text())==dict(binary_sha256=m['reference_binary_sha256'] if name=='OldFull' else m['binary_sha256']),json.loads((case/'config.json').read_text())==cfg,r['strategy']==name,r['status']=='ok',r['verify_every_request']==m['verify'],
                len(events)==len(rows),all(all(row.get(k)==v for k,v in e.items()) for row,e in zip(rows,events)),
                0<=metrics.get('peer_cache_read_bytes',0)<=metrics.get('read_local_bytes',0),
                all(v<=g['local_quota_mib']*MIB for v,g in zip(r['retained_cache_bytes'],cfg['gpus'])),
                sum(g['local_quota_mib'] for g in cfg['gpus'])==24,
                total==r['logical_bytes']==metrics.get('read_bytes',0),len(events)==metrics.get('read_open_count',0),
                total==sum(metrics.get('read_'+tier+'_bytes',0) for tier in ['local','remote','inflight']),
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
            from tail_diagnostic_analysis import read_access_metrics
            access,durable=read_access_metrics(case)
            checks.extend([durable==metrics,r.get('metrics_snapshot')=='after_daemon_shutdown',
                r['request_p99_s']==percentile([row['response_seconds'] for row in rows],.99),
                metrics.get('read_fill_buffer_peak_bytes',0)<=4*MIB,
                metrics.get('inflight_capture_borrowed',0)==metrics.get('inflight_read_open_count',0)])
            from collections import Counter
            expected_access=Counter((f"/gpu0/shard-{e['key']:06d}.tokens",e['caller']) for e in events)
            checks.append(access==dict(expected_access))
            for tier in ['local','remote','inflight']:
                checks.extend([metrics.get('request_cost_'+tier+'_samples',0)==metrics.get(tier+'_read_open_count',0),
                    metrics.get('request_cost_'+tier+'_bytes',0)==metrics.get('read_'+tier+'_bytes',0)])
            if name=='NoAffinity':checks.extend([mechanism(case)['relocated']==0,mechanism(case)['selected_relocations']==0])
            if not all(checks):errors.append(f"{b['id']}/{name}: failed { [i for i,v in enumerate(checks) if not v] }")
            checked+=1
    actual={(p.parent.parent.name,p.parent.name) for p in root.glob('*/*/result.json')}
    if actual-seen:errors.append('unexpected case')
    if list(root.rglob('failure.json')):errors.append('failed attempt present')
    answer=dict(passed=not errors,checked_runs=checked,expected_runs=sum(len(b['variants']) for b in m['spec']['blocks']),errors=errors)
    dump(root/'batch-audit.json',answer);return answer


def mechanism(case):
    events=json.loads((case/'policy-events.json').read_text())
    actions=[(e['action'],e['logical_path'],e['gpu_id']) for e in events if e['action'] in ['PROMOTE_READY','REPLICA_READY','REPLICATE_READY','EVICT']]
    placements=[e for e in events if e['action']=='SHARED_PLACE']
    def fields(e):return dict(x.split('=',1) for x in e['reason'].split(';') if '=' in x)
    displaced=[e for e in events if e['action']=='ADMIT' and float(fields(e).get('displaced',0))+float(fields(e).get('uncertainty',0))>0]
    pending={};committed_relocations=0
    for e in events:
        identity=(e['logical_path'],e['gpu_id'])
        if e['action']=='SHARED_PLACE':pending[identity]=int(fields(e)['caller'])
        if e['action'] in ['PROMOTE_READY','REPLICATE_READY','REPLICA_READY'] and identity in pending:
            committed_relocations+=pending.pop(identity)!=e['gpu_id']
    return dict(action_sha256=digest(actions),placements=len(placements),
        selected_relocations=sum(int(fields(e)['caller'])!=e['gpu_id'] for e in placements),
        relocated=committed_relocations,
        admissions_with_displacement=len(displaced))


def report(root):
    a=audit(root)
    if not a['passed']:raise ValueError(a)
    m=json.loads((root/'manifest.json').read_text());rows=[];pairs=[]
    for b in m['spec']['blocks']:
        rs={n:json.loads((root/b['id']/n/'result.json').read_text()) for n in b['variants']}
        mechanisms={n:mechanism(root/b['id']/n) for n in b['variants']}
        for n,r in rs.items():
            rows.append(dict(block=b['id'],strategy=n,mib_s=r['effective_mib_s'],p99_ms=r['request_p99_s']*1000,
                drain_mib_s=r['logical_bytes']/MIB/r['completed_with_background_s'],
                remote_mib=r['metrics'].get('read_remote_bytes',0)/MIB,inflight_mib=r['metrics'].get('read_inflight_bytes',0)/MIB,
                cpu_s=r['daemon_cpu_s'],**mechanisms[n]))
        for baseline in b['variants'][1:]:
            x=rs['Full'];y=rs[baseline];gain=(y['job_wall_s']/x['job_wall_s']-1)*100
            changed=mechanisms['Full']['action_sha256']!=mechanisms[baseline]['action_sha256']
            active=changed if baseline!='PoolSIEVE1' else True
            if baseline=='NoAffinity':active=active and mechanisms['Full']['relocated']>0 and mechanisms[baseline]['relocated']==0
            if baseline=='NoJoint':active=active and mechanisms['Full']['admissions_with_displacement']>0
            tail=(x['request_p99_s']/y['request_p99_s']-1)*100
            pairs.append(dict(block=b['id'],scenario=b['scenario'],seed=b['seed'],treatment='Full',baseline=baseline,n=1,
                gain_pct=gain,p99_change_pct=tail,drain_gain_pct=(y['completed_with_background_s']/x['completed_with_background_s']-1)*100,
                mechanism_active=active,executed_actions_changed=changed,
                pilot_screen=passes(dict(gain_pct=gain,p99_change_pct=tail,drain_gain_pct=(y['completed_with_background_s']/x['completed_with_background_s']-1)*100,mechanism_active=active,executed_actions_changed=changed,baseline=baseline)),
                acceptance_version='strict-dual-metric-v3',interpretation='hotspot-only development on inspected moving/public/uniform inputs, two reversed-order repeats, retained report70 binary control; not independent confirmation'))
    dump(root/'summary.json',rows);dump(root/'comparisons.json',pairs)
    print(json.dumps(pairs),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('operation',choices=['prepare','run','audit','report']);p.add_argument('--output',type=Path,required=True)
    for name in ['spec','binary','reference-binary','remote-root','freeze']:p.add_argument('--'+name,type=Path)
    args=p.parse_args()
    if args.operation=='prepare':prepare(args.output)
    elif args.operation=='run':run(args)
    elif args.operation=='report':report(args.output)
    else:
        review=audit(args.output);print(json.dumps(review));raise SystemExit(0 if review['passed'] else 1)
