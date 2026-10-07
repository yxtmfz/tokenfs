#!/usr/bin/env python3
"""Read-only, diagnosis-only tail decomposition. Overlap is not causal attribution."""
from __future__ import annotations
import argparse,collections,contextlib,csv,hashlib,json,math,sqlite3,statistics,sys
sys.dont_write_bytecode=True
from pathlib import Path

MIB=1024*1024

def require(value,message):
    if not value:raise ValueError(message)
def read(path):return json.loads(Path(path).read_text())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def percentile(values,p):return sorted(values)[max(0,min(len(values)-1,math.ceil(p*len(values))-1))]
def union_ns(start,end,intervals):
    total=0;last=start
    for a,b in sorted((max(start,a),min(end,b)) for a,b in intervals if a<end and b>start):
        total+=max(0,b-max(a,last));last=max(last,b)
    return total

def sql(case):
    # An archive with WAL must first be handled explicitly: immutable ignores WAL.
    require(not list(case.glob('state.db-*')),'SQLite sidecar present: refuse immutable archive read')
    with contextlib.closing(sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        return ({(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')},
                dict(db.execute('SELECT name,value FROM metrics')))

INDEX_DEFINITIONS={
 'idx_files_shared_precheck_local':"CREATE INDEX idx_files_shared_precheck_local ON files(gpu_id,physical_path,size_bytes) WHERE tier='local' AND state='COMMITTED'",
 'idx_replicas_shared_precheck_ready':"CREATE INDEX idx_replicas_shared_precheck_ready ON local_replicas(logical_path,gpu_id,physical_path,size_bytes) WHERE state='READY'"}

def indexed_schema(case):
    case=Path(case)
    require(not list(case.glob('state.db-*')),'SQLite sidecar present: preserve archive and refuse schema audit')
    with contextlib.closing(sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        require(list(db.execute('PRAGMA quick_check'))==[('ok',)],'SQLite integrity')
        actual={name:definition for name,definition in db.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND name IN ('idx_files_shared_precheck_local','idx_replicas_shared_precheck_ready')")}
    require(actual==INDEX_DEFINITIONS,'actual partial index definitions differ')
    return actual

def analyze_case(case):
    case=Path(case);requests=read(case/'requests.json');trace=read(case/'request-trace.json');result=read(case/'result.json')
    require(trace['clock']=='CLOCK_MONOTONIC' and trace['dropped']==0,'trace clock/dropped')
    require(result['status']=='ok' and result['verify_every_request'] is False,'diagnostic execution status')
    groups=collections.defaultdict(list);handles=collections.defaultdict(list)
    for e in trace['events']:
        require(0<e['start_ns']<=e['end_ns'],'event interval')
        for k in ['wait_ns','pread_ns','flush_ns','copy_ns','verify_ns']:
            require(0<=e[k]<=e['end_ns']-e['start_ns'],k+' duration')
        groups[e['op']].append(e)
        if e['op'] in ['read','release']:handles[e['handle']].append(e)
    opens=sorted(groups['open'],key=lambda e:e['selected_ns'])
    require(len(opens)==len(requests)==len(groups['release']),'open/release count')
    require(len({e['handle'] for e in opens})==len(opens),'unique handles')
    require(set(handles)=={e['handle'] for e in opens},'unknown/missing handle')
    background={name:[(e['start_ns'],e['end_ns']) for e in groups[name]] for name in ['copy_pipeline','copy_attempt','shared_plan']}
    all_releases=[(e['start_ns'],e['end_ns']) for e in groups['release']]
    details=[];seen=collections.Counter();previous=0
    for r,o in zip(requests,opens):
        path=f"/gpu0/shard-{r['key']:06d}.tokens";a=r['start_ns'];b=r['closed_ns']
        require(a<=o['start_ns']<=o['selected_ns']<=o['end_ns']<=r['opened_ns']<=r['read_done_ns']<=b,'open/client order')
        require(o['path']==path and o['caller']==r['caller'],'open/request identity')
        require(r['sha256'] is None,'per-request SHA must be off')
        require(previous<=r['issued_s']<=r['completed_s']<=result['job_wall_s'],'request serial order');previous=r['completed_s']
        require(0<=r['seconds']<=r['response_seconds']+1e-6 and r['response_seconds']<=r['completed_s']-r['issued_s']+1e-6,'response interval')
        related=handles[o['handle']];reads=[e for e in related if e['op']=='read'];release=[e for e in related if e['op']=='release']
        require(len(release)==1 and reads,'release/read presence');rel=release[0]
        require(all(e['path']==path and e['caller']==r['caller'] and e['tier']==o['tier'] for e in related),'handle source identity')
        require(sum(e['bytes'] for e in reads)==r['bytes'],'read bytes')
        require(all(r['opened_ns']<=e['start_ns']<=e['end_ns']<=r['read_done_ns'] for e in reads),'read timing')
        require(rel['start_ns']>=max(e['end_ns'] for e in reads),'release timing')
        foreground=[(o['start_ns'],o['end_ns'])]+[(e['start_ns'],e['end_ns']) for e in related]
        last_data=max((e for e in reads if e['bytes']>0),key=lambda e:e['end_ns'])
        ns=dict(client_open=r['opened_ns']-a,client_read=r['read_done_ns']-r['opened_ns'],client_close=b-r['read_done_ns'],
                daemon_open=o['end_ns']-o['start_ns'],open_layout_wait=o['wait_ns'],
                daemon_read=sum(e['end_ns']-e['start_ns'] for e in reads),pread=sum(e['pread_ns'] for e in reads),
                read_non_pread=sum(e['end_ns']-e['start_ns']-e['pread_ns'] for e in reads),
                last_data_read=last_data['end_ns']-last_data['start_ns'],last_data_pread=last_data['pread_ns'],
                last_data_non_pread=last_data['end_ns']-last_data['start_ns']-last_data['pread_ns'],
                eof_non_pread=sum(e['end_ns']-e['start_ns']-e['pread_ns'] for e in reads if e['bytes']==0),
                daemon_release=rel['end_ns']-rel['start_ns'],release_wait=rel['wait_ns'],release_flush=rel['flush_ns'],
                release_inside_client=union_ns(a,b,[(rel['start_ns'],rel['end_ns'])]),
                release_after_close=max(0,rel['end_ns']-max(b,rel['start_ns'])),
                all_release_overlap=union_ns(a,b,all_releases),
                foreground_union=union_ns(a,b,foreground),client_unattributed=b-a-union_ns(a,b,foreground))
        for name,intervals in background.items():ns[name+'_overlap']=union_ns(a,b,intervals)
        ns['same_key_copy_overlap']=union_ns(a,b,[(e['start_ns'],e['end_ns']) for e in groups['copy_pipeline'] if e['path']==path])
        ns['other_key_copy_overlap']=union_ns(a,b,[(e['start_ns'],e['end_ns']) for e in groups['copy_pipeline'] if e['path']!=path])
        ns['getattr_overlap']=union_ns(a,b,[(e['start_ns'],e['end_ns']) for e in groups['getattr'] if e['path']==path])
        row=dict(index=r['index'],key=r['key'],caller=r['caller'],tier=o['tier'],location=o.get('location',-1),handle=o['handle'],
                 physical_pread_ops=None,physical_pread_bytes=None,
                 occurrence=seen[r['key']]+1,access_class='reused' if seen[r['key']] else 'first',read_callbacks=len(reads),
                 response_ms=r['response_seconds']*1000,client_ms=(b-a)/1e6,
                 ipc_scheduling_ms=r['response_seconds']*1000-(b-a)/1e6,**{k+'_ms':v/1e6 for k,v in ns.items()})
        seen[r['key']]+=1;details.append(row)
    metrics=result['metrics'];access,durable=sql(case)
    require(durable==metrics and result.get('metrics_snapshot')=='after_daemon_shutdown','durable metrics')
    require(access==dict(collections.Counter((f"/gpu0/shard-{r['key']:06d}.tokens",r['caller']) for r in requests)),'access accounting')
    require(sum(e['bytes'] for e in groups['read'])==result['logical_bytes']==metrics['read_bytes'],'total bytes')
    for tier in ['remote','local','inflight']:
        require(sum(e['bytes'] for e in groups['read'] if e['tier']==tier)==metrics.get('read_'+tier+'_bytes',0),tier+' accounting')
        require(metrics.get('request_cost_'+tier+'_samples',0)==metrics.get(tier+'_read_open_count',0),'cost sample '+tier)
        require(metrics.get('request_cost_'+tier+'_bytes',0)==metrics.get('read_'+tier+'_bytes',0),'cost bytes '+tier)
    require(len(opens)==metrics['read_open_count'],'open count')
    require(metrics.get('background_submitted',0)==metrics.get('background_completed',0),'background drain')
    require(not any(v for k,v in metrics.items() if k.endswith('error_count')),'error counter')
    require(metrics.get('read_fill_buffer_peak_bytes',0)<=4*MIB,'capture memory cap')
    require(result['request_p99_s']==percentile([r['response_seconds'] for r in requests],.99),'p99 recompute')
    require(abs(result['effective_mib_s']-result['logical_bytes']/MIB/result['job_wall_s'])<1e-8,'rate recompute')
    require(len(background['copy_pipeline'])==metrics.get('promote_count',0)+metrics.get('cross_gpu_replica_create_count',0),'copy count')
    tail=sorted(details,key=lambda r:r['response_ms'],reverse=True)[:math.ceil(len(details)*.01)]
    def summarize(rows):
        if not rows:return dict(n=0)
        return dict(n=len(rows),response_p99_ms=percentile([r['response_ms'] for r in rows],.99),
                    means={k:statistics.mean(r[k] for r in rows) for k in details[0] if k.endswith('_ms')})
    strata=[dict(access_class=c,tier=t,**summarize([r for r in details if r['access_class']==c and r['tier']==t]))
            for c in ['first','reused'] for t in ['remote','local','inflight']]
    return dict(diagnosis_only=True,performance_evidence=False,passed=True,requests=len(details),
                event_count=len(trace['events']),dropped=trace['dropped'],top_count=len(tail),
                groups={name:summarize([r for r in details if name=='all' or r['access_class']==name]) for name in ['all','first','reused']},
                top12=tail,strata=strata,details=details,operation_counts={k:len(v) for k,v in groups.items()},
                physical_pread_ops=metrics.get('direct_backend_pread_ops',0),physical_pread_bytes=metrics.get('direct_backend_pread_bytes',0),
                extra_tail_buffer_bytes_peak=metrics.get('direct_read_tail_buffer_bytes_peak',0),
                control_counters={k:metrics.get(k,0) for k in ['background_submitted','background_completed','read_fill_capture_complete','read_fill_capture_us','shared_placement_no_gain','shared_placement_coalesced','shared_placement_selected']},
                top12_read_callbacks={str(r['index']):[dict(bytes=e['bytes'],duration_ms=(e['end_ns']-e['start_ns'])/1e6,pread_ms=e['pread_ns']/1e6,non_pread_ms=(e['end_ns']-e['start_ns']-e['pread_ns'])/1e6) for e in sorted(handles[r['handle']],key=lambda e:e['start_ns']) if e['op']=='read'] for r in tail},
                copy_mean_ms=statistics.mean((b-a)/1e6 for a,b in background['copy_pipeline']) if background['copy_pipeline'] else 0,
                notes='Diagnostic overhead enabled. No performance acceptance. Copy/plan/release overlaps are unions per category and may overlap each other; do not add them. Release may finish after client close; flush is its total, not a known in-request subinterval. First/reused means prior access to this object in this fixed trace, not an inferred cache miss. Read non-pread residual includes allocation, copying, counters, capture and scheduling; there is no standalone SubmitBackground timestamp, so it cannot be attributed solely to SQLite fsync.')

def paired_requests(left,right,left_name='Full',right_name='NoHotspot'):
    a=left['details'];b=right['details'];require(len(a)==len(b)==1152,'paired request count')
    selected=sorted({x['index'] for x in left['top12']+right['top12']})
    require(12<=len(selected)<=24,'both top12 union size')
    answer=[]
    fields=['tier','location','occurrence','access_class','response_ms','client_open_ms','client_read_ms',
            'client_close_ms','daemon_open_ms','open_layout_wait_ms','pread_ms','daemon_read_ms',
            'read_non_pread_ms','release_inside_client_ms','release_after_close_ms',
            'copy_pipeline_overlap_ms','copy_attempt_overlap_ms','shared_plan_overlap_ms',
            'physical_pread_ops','physical_pread_bytes']
    for x,y in zip(a,b):
        require(all(x[k]==y[k] for k in ['index','key','caller','occurrence','access_class']),'same ordinal/key/caller mismatch')
        row={k:x[k] for k in ['index','key','caller','occurrence','access_class']}
        row.update(left_arm=left_name,right_arm=right_name,top12_union=x['index'] in selected)
        for k in fields:row['left_'+k]=x[k];row['right_'+k]=y[k]
        row['left_minus_right_response_ms']=x['response_ms']-y['response_ms'];answer.append(row)
    return dict(left=left_name,right=right_name,all_requests=answer,top12_union=[answer[i] for i in selected],
                matched_by='logical ordinal/key/caller; realized route is separately recorded for each arm',
                physical_IO_per_request_available=False)

def analyze(root,output):
    root=Path(root).resolve();output=Path(output).resolve()
    require(root!=output and root not in output.parents,'analysis output must be outside evidence')
    m=read(root/'manifest.json');require(m['diagnosis_only'] and not m['performance_evidence'],'diagnostic label')
    require(m['order']==['Full','NoHotspot'] and m['spec']['requests']==1152,'fixed diagnosis matrix')
    for relative,expected in read(root/'receipts.json')['files'].items():require(sha(root/relative)==expected,'receipt '+relative)
    result={name:analyze_case(root/name) for name in m['order']}
    require(all(r['requests']==1152 and r['top_count']==12 for r in result.values()),'full fixed trace/top12')
    paired=paired_requests(result['Full'],result['NoHotspot'])
    for arm in m['order']:
        indexed_schema(root/arm)
        require(read(root/arm/'result.json')['metrics'].get('read_release_count')==1152,'80 release fence')
    output.mkdir(parents=True,exist_ok=False)
    summary={name:{k:v for k,v in r.items() if k!='details'} for name,r in result.items()}
    dump(output/'analysis.json',summary)
    dump(output/'same-ordinal-top12-union.json',{k:v for k,v in paired.items() if k!='all_requests'})
    for name,data in [('same-ordinal-all.tsv',paired['all_requests']),('same-ordinal-top12-union.tsv',paired['top12_union'])]:
        with (output/name).open('w',newline='') as handle:
            writer=csv.DictWriter(handle,delimiter='\t',fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    for name,r in result.items():
        with (output/(name+'-requests.csv')).open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=list(r['details'][0]));writer.writeheader();writer.writerows(r['details'])
    lines=['# Diagnosis only: moving74801 tail decomposition','','Tracing changes timings. These two arms do not replace the frozen speed tables. Overlap is association, not proof of causality.','']
    for name,r in result.items():
        lines += ['## '+name,'','| index | class | tier | response ms | open ms | read ms | pread ms | release in client ms | copy overlap ms |','|---:|---|---|---:|---:|---:|---:|---:|---:|']
        for row in r['top12']:
            lines.append('| {index} | {access_class} | {tier} | {response_ms:.3f} | {client_open_ms:.3f} | {client_read_ms:.3f} | {pread_ms:.3f} | {release_inside_client_ms:.3f} | {copy_pipeline_overlap_ms:.3f} |'.format(**row))
        lines+=['',r['notes'],'']
    (output/'tail-top12.md').write_text('\n'.join(lines)+'\n')
    return dict(passed=True,diagnosis_only=True,arms=list(result),requests=sum(r['requests'] for r in result.values()))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();print(json.dumps(analyze(a.evidence,a.output)))
