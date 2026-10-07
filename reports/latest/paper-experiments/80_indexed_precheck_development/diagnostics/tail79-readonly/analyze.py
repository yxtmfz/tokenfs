#!/usr/bin/env python3
"""Read-only batch79 tail diagnosis. Does not infer reused tiers from latency."""
from pathlib import Path
import argparse,collections,contextlib,csv,hashlib,json,math,sqlite3,statistics

HERE=Path(__file__).resolve().parent
MIB=1024*1024
PRIMARY=['NoHotspot','NoAffinity','NoJoint','PoolSIEVE1']
def load(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def hashes(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

def read_case(case):
    rows=load(case/'requests.json');result=load(case/'result.json');cfg=load(case/'config.json')
    assert result['status']=='ok' and not result['verify_every_request'] and len(rows)==1152
    assert not cfg['policy'].get('prefetch_on_read') and not cfg['policy'].get('request_trace_path') and not cfg['policy'].get('profile_control_path')
    sidecars=sorted(case.glob('state.db-*'))
    assert not sidecars or ({p.name for p in sidecars}=={'state.db-wal','state.db-shm'} and (case/'state.db-wal').stat().st_size==0 and (case/'state.db-shm').stat().st_size==32768)
    with contextlib.closing(sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        assert list(db.execute('PRAGMA quick_check'))==[('ok',)]
        metrics=dict(db.execute('SELECT name,value FROM metrics'));assert metrics==result['metrics']
        access={(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}
        assert access==dict(collections.Counter((f"/gpu0/shard-{r['key']:06d}.tokens",r['caller']) for r in rows))
        schemas={name:sql for name,sql in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'")}
    ranked=sorted(rows,key=lambda r:(-r['response_seconds'],r['index']))
    rank={r['index']:i+1 for i,r in enumerate(ranked)}
    p99_rank=len(rows)-math.ceil(.99*len(rows))+1
    assert p99_rank==12 and ranked[p99_rank-1]['response_seconds']==result['request_p99_s']
    annotated=[];seen={};seen_by_caller=set()
    for row in rows:
        i=row['index'];assert i==len(annotated)
        annotated.append(dict(row,global_first=row['key'] not in seen,
            first_for_caller=(row['key'],row['caller']) not in seen_by_caller,
            previous_same_key_index=seen.get(row['key']),rank_from_slowest=rank[i],
            tier_evidence='remote_from_fresh_cache_no_prefetch_protocol' if row['key'] not in seen else 'unknown_remote_local_or_RAM',
            physical_pread_ops=None,physical_pread_bytes=None))
        seen[row['key']]=i;seen_by_caller.add((row['key'],row['caller']))
    top=[annotated[row['index']] for row in ranked[:12]]
    neighbors=[annotated[row['index']] for row in ranked[9:14]]
    first=sum(r['global_first'] for r in annotated)
    remote=metrics.get('remote_read_open_count',0);local=metrics.get('local_read_open_count',0);ram=metrics.get('inflight_read_open_count',0)
    assert remote>=first and remote+local+ram==len(rows)
    repeated_counts={'remote':remote-first,'local':local,'RAM':ram}
    unknown=sum(not r['global_first'] for r in top)
    lower={tier:max(0,unknown-(len(rows)-first-count)) for tier,count in repeated_counts.items()}
    upper={tier:min(unknown,count) for tier,count in repeated_counts.items()}
    # Every first occurrence must come from the remote source in a fresh,
    # demand-only run. A latency threshold is not a route label for a reuse.
    summary=dict(first_requests=first,reused_requests=len(rows)-first,
        p99_ms=result['request_p99_s']*1000,p99_rank_from_slowest=p99_rank,
        top12_first_remote_inferred=len(top)-unknown,top12_reused_tier_unknown=unknown,
        top12_first_remote_fraction=(len(top)-unknown)/12,
        top12_reused_fraction=unknown/12,
        repeated_tier_totals_from_aggregate_accounting=repeated_counts,
        top12_layer_bounds=dict(remote=[len(top)-unknown+lower['remote'],len(top)-unknown+upper['remote']],local=[lower['local'],upper['local']],RAM=[lower['RAM'],upper['RAM']]),
        top12_bounds_are_not_jointly_independent=True,top12=top,p99_neighbors=neighbors,
        service_requests=dict(remote=remote,local=local,RAM=ram),
        physical_pread_ops=metrics.get('direct_backend_pread_ops',0),physical_pread_bytes=metrics.get('direct_backend_pread_bytes',0),
        tail_hits=metrics.get('direct_read_tail_hits',0),tail_bytes=metrics.get('direct_read_tail_bytes',0),
        wall_s=result['job_wall_s'],response_sum_s=math.fsum(r['response_seconds'] for r in rows),
        response_loop_overhead_s=result['job_wall_s']-math.fsum(r['response_seconds'] for r in rows),
        sql_metric_and_access_exact=True,request_fields=sorted(rows[0]),sql_tables=schemas)
    return annotated,result,summary

def main(evidence):
    evidence=evidence.resolve();before=hashes(evidence);development=evidence/'development'
    records=load(development/'comparisons.json')
    failed=[p for p in records if p['baseline'] in PRIMARY and not p['pilot_screen']]
    assert len(failed)==5
    cases={};summaries={};details=[]
    for pair in failed:
        for arm in ['Full',pair['baseline']]:
            key=pair['block']+'/'+arm
            if key not in cases:
                rows,result,summary=read_case(development/key);cases[key]=(rows,result);summaries[key]=summary
        x,xr=cases[pair['block']+'/Full'];y,yr=cases[pair['block']+'/'+pair['baseline']]
        assert all(all(a[k]==b[k] for k in ['index','key','caller','bytes']) for a,b in zip(x,y))
        gain=(yr['job_wall_s']/xr['job_wall_s']-1)*100
        reduction=(1-xr['request_p99_s']/yr['request_p99_s'])*100
        drain=(yr['completed_with_background_s']/xr['completed_with_background_s']-1)*100
        assert gain==pair['gain_pct'] and -reduction==pair['p99_change_pct'] and drain==pair['drain_gain_pct']
        xs=summaries[pair['block']+'/Full'];ys=summaries[pair['block']+'/'+pair['baseline']]
        def matched(index):
            a=x[index];b=y[index]
            return dict(index=index,key=a['key'],caller=a['caller'],global_first=a['global_first'],
                tier_evidence=a['tier_evidence'],Full_rank=a['rank_from_slowest'],baseline_rank=b['rank_from_slowest'],
                Full_response_ms=a['response_seconds']*1000,baseline_response_ms=b['response_seconds']*1000,
                Full_worker_ms=a['seconds']*1000,baseline_worker_ms=b['seconds']*1000,
                Full_minus_baseline_ms=(a['response_seconds']-b['response_seconds'])*1000,
                Full_physical_ops=None,baseline_physical_ops=None,
                Full_physical_bytes=None,baseline_physical_bytes=None)
        all_rows=[matched(i) for i in range(len(x))]
        output=HERE/'same-request'/(pair['block']+'--'+pair['baseline']+'.tsv');output.parent.mkdir(exist_ok=True)
        with output.open('w') as handle:
            writer=csv.DictWriter(handle,delimiter='\t',fieldnames=list(all_rows[0]));writer.writeheader();writer.writerows(all_rows)
        categories={}
        for label,first in [('cold_remote_protocol_inferred',True),('reused_route_unidentified',False)]:
            selected=[r for r in all_rows if r['global_first']==first]
            categories[label]=dict(requests=len(selected),Full_sum_ms=math.fsum(r['Full_response_ms'] for r in selected),baseline_sum_ms=math.fsum(r['baseline_response_ms'] for r in selected),Full_minus_baseline_ms=math.fsum(r['Full_minus_baseline_ms'] for r in selected))
        loop=(xs['response_loop_overhead_s']-ys['response_loop_overhead_s'])*1000
        wall=(xr['job_wall_s']-yr['job_wall_s'])*1000
        assert abs(wall-(loop+math.fsum(v['Full_minus_baseline_ms'] for v in categories.values())))<1e-8
        details.append(dict(block=pair['block'],baseline=pair['baseline'],throughput_gain_pct=gain,p99_reduction_pct=reduction,drain_gain_pct=drain,
            Full_p99_request=matched(xs['top12'][-1]['index']),baseline_p99_request=matched(ys['top12'][-1]['index']),
            Full_top12_same_indices=[matched(r['index']) for r in xs['top12']],
            baseline_top12_same_indices=[matched(r['index']) for r in ys['top12']],
            p99_neighbor_union=[matched(i) for i in sorted({r['index'] for r in xs['p99_neighbors']+ys['p99_neighbors']})],
            category_response_sums=categories,loop_overhead_delta_ms=loop,wall_delta_ms=wall,
            request_matching='same logical ordinal/key/caller only; not the same realized backend path or clock sample',
            same_request_table=str(output.relative_to(HERE)),
            physical_io_comparison=dict(Full=dict(ops=xs['physical_pread_ops'],bytes=xs['physical_pread_bytes']),baseline=dict(ops=ys['physical_pread_ops'],bytes=ys['physical_pread_bytes']),per_request_mapping_available=False)))
    assert hashes(evidence)==before
    result=dict(diagnosis_only=True,performance_tables_and_acceptance_unchanged=True,raw_evidence_unchanged=True,
        failed_primary_comparisons=5,unique_cases=len(cases),same_request_rows=len(failed)*1152,
        first_access_tier_is_protocol_inference_not_recorded_trace=True,
        repeated_request_tier_mapping_available=False,per_request_physical_IO_mapping_available=False,
        limitations=['Request rows contain logical ordinal/key/caller and timings, not handle/tier/pread events.',
          'Durable metrics are end-of-run aggregates; gpu_access is per-key/domain total. gpu_access_events contains coarse access timestamps but no source tier/handle.',
          'policy_events has event order but no timing or request/handle ID; asynchronous READY/eviction events cannot safely be assigned to a request ordinal.',
          'Do not label a reused request remote/local/RAM by latency thresholds. Top12 layer ranges are bounds, not exact classifications.',
          'Same ordinal comparisons include different prior online policy/cost histories and external service samples. Counter differences alone cannot identify one cause.',
          'Cold first requests cannot become cache hits under the frozen fresh-cache/no-prefetch protocol. Their response may still change through control cost, concurrent copy work or remote service/scheduling.'],
        cases=summaries,pairs=details)
    dump(HERE/'analysis.json',result);dump(HERE/'evidence-hashes.json',before)
    print(json.dumps(dict(passed=True,failed_comparisons=5,unique_cases=len(cases),matched_rows=len(failed)*1152,raw_unchanged=True)))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--evidence',type=Path,required=True)
    main(parser.parse_args().evidence)
