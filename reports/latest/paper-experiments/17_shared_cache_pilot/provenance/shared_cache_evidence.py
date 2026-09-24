#!/usr/bin/env python3
"""Offline evidence check; does not execute benchmarks or alter the raw cases."""
import argparse,json,math,statistics,sys
from pathlib import Path
import shared_cache_pilot as study
from evidence_benchmark import sha,dump,MIB

def review(data,source,freeze):
    frozen=json.loads(freeze.read_text());errors=[];stages={}
    def check(ok,where):
        if not ok:errors.append(where)
    for stage,count in [('correctness',3),('development',18)]:
        root=data/stage;m=json.loads((root/'manifest.json').read_text())
        a=study.audit(root);stages[stage]=a
        check(a['passed'] and a['checked_runs']==count,stage+': audit/count')
        check(m['binary_sha256']==frozen['binary_sha256'],stage+': binary')
        check(m['source_hashes']==frozen['source_hashes'],stage+': source manifest')
        for name,value in m['source_hashes'].items():
            check(sha(source/name)==value,stage+': source '+name)
        spec=source/f'study-configs/shared-cache-pilot-{stage}.json'
        check(sha(spec)==frozen['specs'][stage],stage+': frozen spec')
        check(json.loads(spec.read_text())==m['spec'],stage+': manifest spec')
        if stage=='development':
            check(m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(','),stage+': transport')
        for b in m['spec']['blocks']:
            for arm in study.VARIANTS:
                r=json.loads((root/b['id']/arm/'result.json').read_text())
                metrics=r['metrics'];peer=metrics.get('peer_cache_read_bytes',0)
                check(peer==metrics.get('peer_cache_hit',0)*b['shard_mib']*MIB,b['id']+'/'+arm+': peer bytes')
                if b['scenario']=='disjoint':check(peer==0,b['id']+'/'+arm+': negative-control peer hit')
    root=data/'development';m=json.loads((root/'manifest.json').read_text())
    rs={(p.parent.parent.name,p.parent.name):json.loads(p.read_text()) for p in root.glob('*/*/result.json')}
    summaries=json.loads((root/'summary.json').read_text());comparisons=json.loads((root/'comparisons.json').read_text())
    check(len(summaries)==6 and len(comparisons)==6,'derived row counts')
    for row in summaries:
        vals=[rs[b['id'],row['strategy']] for b in m['spec']['blocks'] if b['scenario']==row['scenario']]
        fns=dict(mib_s=lambda r:r['logical_bytes']/MIB/r['job_wall_s'],wall_s=lambda r:r['job_wall_s'],cpu_s=lambda r:r['daemon_cpu_s'],p99_ms=lambda r:r['request_p99_s']*1000,remote_mib=lambda r:r['metrics'].get('read_remote_bytes',0)/MIB,copy_mib=lambda r:sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB,peer_mib=lambda r:r['metrics'].get('peer_cache_read_bytes',0)/MIB,peer_hits=lambda r:r['metrics'].get('peer_cache_hit',0))
        for k,fn in fns.items():check(math.isclose(row[k],statistics.mean(fn(r) for r in vals),rel_tol=1e-12,abs_tol=1e-12),f'{row["scenario"]}/{row["strategy"]}: derived {k}')
    for row in comparisons:
        blocks=[b for b in m['spec']['blocks'] if b['scenario']==row['scenario']]
        vals=[(rs[b['id'],row['treatment']],rs[b['id'],row['baseline']]) for b in blocks]
        ratios=[y['job_wall_s']/x['job_wall_s'] for x,y in vals]
        expected=(math.prod(ratios)**(1/len(ratios))-1)*100
        check(math.isclose(expected,row['paired_change_pct'],abs_tol=1e-10),'paired gain')
        check(row['n']==3 and row['wins']==sum(x>1 for x in ratios),'paired count/wins')
        for b,v,per in zip(blocks,ratios,row['per_seed']):check(b['seed']==per['seed'] and math.isclose((v-1)*100,per['change_pct'],abs_tol=1e-10),'per-seed gain')
        drain=(math.prod(y['completed_with_background_s']/x['completed_with_background_s'] for x,y in vals)**(1/len(vals))-1)*100
        check(math.isclose(drain,row['with_drain_change_pct'],abs_tol=1e-10),'drain gain')
    shared=next(x for x in comparisons if x['scenario']=='shared_capacity' and x['treatment']=='AnyReadyShare' and x['baseline']=='OwnerShare')
    neg=next(x for x in comparisons if x['scenario']=='disjoint' and x['treatment']=='AnyReadyShare' and x['baseline']=='OwnerShare')
    sm={r['strategy']:r for r in summaries if r['scenario']=='shared_capacity'}
    gates=dict(all_three_shared_faster=shared['wins']==3,shared_gain_at_least_5pct=shared['paired_change_pct']>=5,peer_active=sm['AnyReadyShare']['peer_mib']>0,remote_bytes_reduced=sm['AnyReadyShare']['remote_mib']<sm['OwnerShare']['remote_mib'],disjoint_regression_no_more_3pct=neg['paired_change_pct']>=-3)
    return dict(passed=not errors,errors=errors,stages=stages,checked_speed_runs=18,checked_content_runs=3,followup_gates=gates,promising_pilot=not errors and all(gates.values()),interpretation='storage-path pilot only; no formal significance, GPU inference, novel affinity or H/P synergy claim; expansion requires user approval')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--freeze',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=review(a.data_root,a.source_root,a.freeze);dump(a.output,result);print(json.dumps(result));sys.exit(0 if result['passed'] else 1)
