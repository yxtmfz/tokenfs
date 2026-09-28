"""Correlate monotonic client intervals and daemon handles; overlap is not causality."""
import json,math,statistics,sqlite3
from collections import Counter,defaultdict
from pathlib import Path

def intersection_ns(start,end,intervals):
    clipped=sorted((max(start,a),min(end,b)) for a,b in intervals if a<end and b>start)
    total=0;last=start
    for a,b in clipped:
        total+=max(0,b-max(a,last));last=max(last,b)
    return total

def analyze_case(case):
    case=Path(case)
    load=lambda n:json.loads((case/n).read_text())
    requests=load('requests.json');trace=load('request-trace.json');result=load('result.json')
    assert trace['clock']=='CLOCK_MONOTONIC' and trace['dropped']==0
    events=trace['events'];groups=defaultdict(list)
    for e in events:
        assert 0<e['start_ns']<=e['end_ns']
        for k in ['wait_ns','pread_ns','flush_ns','copy_ns','verify_ns']:
            assert 0<=e[k]<=e['end_ns']-e['start_ns']
        groups[e['op']].append(e)
    opens=sorted(groups['open'],key=lambda e:e['start_ns'])
    assert len(opens)==len(requests)==len(groups['release'])
    assert len({e['handle'] for e in opens})==len(opens)
    handles=defaultdict(list)
    for e in groups['read']+groups['release']:handles[e['handle']].append(e)
    assert set(handles)=={e['handle'] for e in opens}
    copies=[(e['start_ns'],e['end_ns']) for e in groups['copy_pipeline']]
    metrics=result['metrics']
    assert len(copies)==metrics.get('promote_count',0)+metrics.get('cross_gpu_replica_create_count',0)
    rows=[]
    for r,o in zip(requests,opens):
        path=f"/gpu0/shard-{r['key']:06d}.tokens"
        assert r['start_ns']<=o['start_ns']<=o['end_ns']<=r['opened_ns']<=r['read_done_ns']<=r['closed_ns']
        assert o['path']==path and o['caller']==r['caller']
        related=handles[o['handle']];reads=[e for e in related if e['op']=='read']
        release=[e for e in related if e['op']=='release'];assert len(release)==1
        rel=release[0]
        assert all(e['path']==path and e['caller']==r['caller'] and e['tier']==o['tier'] for e in related)
        assert sum(e['bytes'] for e in reads)==r['bytes']
        assert all(r['opened_ns']<=e['start_ns']<=e['end_ns']<=r['read_done_ns'] for e in reads)
        assert rel['start_ns']>=max(e['end_ns'] for e in reads)
        ns=dict(client_open=r['opened_ns']-r['start_ns'],client_read=r['read_done_ns']-r['opened_ns'],
          client_close=r['closed_ns']-r['read_done_ns'],daemon_open=o['end_ns']-o['start_ns'],
          layout_wait=o['wait_ns'],pread=sum(e['pread_ns'] for e in reads),pread_max=max(e['pread_ns'] for e in reads),
          daemon_read=sum(e['end_ns']-e['start_ns'] for e in reads),release=rel['end_ns']-rel['start_ns'],
          metric_flush=rel['flush_ns'],release_wait=rel['wait_ns'],
          copy_overlap=intersection_ns(r['start_ns'],r['closed_ns'],copies),
          release_after_close=max(0,rel['end_ns']-r['closed_ns']))
        ns['client_unattributed']=r['closed_ns']-r['start_ns']-ns['daemon_open']-ns['daemon_read']
        # Release can be asynchronous relative to close(2): do not subtract it twice.
        row=dict(index=r['index'],key=r['key'],caller=r['caller'],tier=o['tier'],handle=o['handle'],
          response_ms=r['response_seconds']*1000,client_ms=(r['closed_ns']-r['start_ns'])/1e6,
          ipc_scheduling_ms=r['response_seconds']*1000-(r['closed_ns']-r['start_ns'])/1e6,
          **{k+'_ms':v/1e6 for k,v in ns.items()})
        rows.append(row)
    assert sum(e['bytes'] for e in groups['read'])==result['logical_bytes']==metrics['read_bytes']
    assert sum(e['bytes'] for e in groups['read'] if e['tier']=='remote')==metrics['read_remote_bytes']
    counts=Counter((f"/gpu0/shard-{r['key']:06d}.tokens",r['caller']) for r in requests)
    with sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
        assert dict(((p,g),n) for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access'))==dict(counts)
        assert dict(db.execute('SELECT name,value FROM metrics'))==metrics
    tail=sorted(rows,key=lambda r:r['response_ms'],reverse=True)[:math.ceil(len(rows)*.01)]
    keys=[k for k in rows[0] if k.endswith('_ms')]
    summarize=lambda rs:{k:statistics.mean(r[k] for r in rs) for k in keys} if rs else None
    strata=[]
    for tier in ['local','remote']:
        for overlap in [False,True]:
            rs=[r for r in rows if r['tier']==tier and (r['copy_overlap_ms']>0)==overlap]
            strata.append(dict(tier=tier,overlap=overlap,n=len(rs),means=summarize(rs)))
    return dict(passed=True,requests=len(rows),event_count=len(events),dropped=trace['dropped'],
      diagnostic_mib_s=result['effective_mib_s'],p99_ms=result['request_p99_s']*1000,
      all_means=summarize(rows),tail_means=summarize(tail),tail_requests=tail,
      strata=strata,request_details=rows,copy_count=len(copies),
      copy_mean_ms=statistics.mean((b-a)/1e6 for a,b in copies) if copies else 0,
      copy_io_mean_ms=statistics.mean(e['copy_ns']/1e6 for e in groups['copy_pipeline']) if copies else 0,
      copy_verify_mean_ms=statistics.mean(e['verify_ns']/1e6 for e in groups['copy_pipeline']) if copies else 0,
      limitation='Diagnostic timing only. Concurrent copy overlap is association, not a causal attribution. Release may finish after client close.')
