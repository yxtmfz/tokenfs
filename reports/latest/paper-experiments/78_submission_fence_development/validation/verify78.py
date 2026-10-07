#!/usr/bin/env python3
"""Offline review of the frozen 24-run submission-fence HPJ study.

ROOT directly contains development/, correctness/ and provenance/freeze.json.
The evidence and source archive are read-only inputs; all source audit/report
writes occur on a temporary copy. Four primary HPJ/SIEVE contrasts and a separate submission-telemetry diagnostic are retained.
"""
from __future__ import annotations
import argparse,collections,contextlib,hashlib,importlib,io,json,math,random
import shutil,sqlite3,statistics,sys,tarfile,tempfile
from pathlib import Path

MIB=1024*1024
PRIMARY_PAIRS=[('Full','NoHotspot'),('Full','NoAffinity'),('Full','NoJoint'),('Full','PoolSIEVE1')]
PAIRS=PRIMARY_PAIRS+[('Full','SyncSubmission')]

def require(condition,message):
    if not condition:raise ValueError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def percentile(values,p):return sorted(values)[max(0,min(len(values)-1,math.ceil(p*len(values))-1))]

def tree_hashes(root):
    return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}

def extract_source(archive,target):
    with tarfile.open(archive) as handle:
        members=handle.getmembers();seen=set()
        for member in members:
            path=Path(member.name)
            require(not path.is_absolute() and '..' not in path.parts,'unsafe source archive path')
            require(member.isfile() or member.isdir(),'source archive links/special files unsupported')
            require(member.name not in seen,'duplicate source archive path');seen.add(member.name)
        handle.extractall(target,members=members)

def sqlite_bundle_files(case):
    case=Path(case);sidecars=sorted(case.glob('state.db-*'))
    if sidecars:
        require({p.name for p in sidecars}=={'state.db-wal','state.db-shm'},f'{case}: incomplete/unknown SQLite sidecars')
        require((case/'state.db-wal').stat().st_size==0,f'{case}: nonempty WAL cannot be read immutably')
        require((case/'state.db-shm').stat().st_size==32768,f'{case}: unexpected SHM size')
    return [case/'state.db']+sidecars

def verify_sqlite_preservation(evidence):
    evidence=Path(evidence);files={};bundles={}
    for database in sorted(evidence.rglob('state.db')):
        preserved={str(p.relative_to(evidence)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in sqlite_bundle_files(database.parent)}
        files.update(preserved)
        bundles[str(database.relative_to(evidence))]=preserved
    sidecars={str(p.relative_to(evidence)) for p in evidence.rglob('state.db-*')}
    require(sidecars=={p for p in files if Path(p).name!='state.db'},'unaccounted SQLite sidecars')
    receipt=read(evidence/'provenance/sqlite-sidecars.json')
    require(receipt['format']==1 and receipt['checked_databases']==len(bundles)==30 and
            receipt['sidecar_files']==len(sidecars) and receipt['files']==files and
            receipt['original_sql_files_unchanged'] is True,'SQLite preservation receipt mismatch')
    require(set(receipt['bundles'])==set(bundles),'SQLite bundle receipt set')
    for name,preserved in bundles.items():
        mode='paired_empty_wal_preserved' if len(preserved)==3 else 'no_sidecars'
        require(receipt['bundles'][name]==dict(files=preserved,sidecar_mode=mode,immutable_sql_matches=True),'SQLite bundle receipt mismatch: '+name)
    return dict(databases=len(bundles),sidecar_files=len(sidecars),empty_wal_pairs=len(sidecars)//2,
                all_original_components_preserved=True,sqlite_read_mode='immutable only after WAL confirmed absent or zero-byte')

def archived_sql(case):
    case=Path(case);sqlite_bundle_files(case)
    # Empty WAL has no frames. Preserve WAL/SHM in raw evidence, but read the
    # main database immutably to avoid creating/modifying SQLite sidecars.
    with contextlib.closing(sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        require(list(db.execute('PRAGMA quick_check'))==[('ok',)],f'{case}: SQLite quick_check')
        access={(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}
        metrics=dict(db.execute('SELECT name,value FROM metrics'))
    return access,metrics

def expected_objects(spec,events):
    result={}
    for key in sorted({e['key'] for e in events}):
        payload=random.Random(spec['seed']*100000+key).randbytes(MIB)
        result[str(key)]=hashlib.sha256(payload*spec['shard_mib']).hexdigest()
    return result

def verify_rows(case,events,expected,config,binary,verify_content):
    result=read(case/'result.json');rows=read(case/'requests.json');metrics=result['metrics']
    require(result['status']=='ok' and result['verify_every_request']==verify_content,f'{case}: result status')
    require(read(case/'execution.json')=={'binary_sha256':binary},f'{case}: binary receipt')
    require(read(case/'config.json')==config,f'{case}: config mismatch')
    require(len(rows)==len(events),f'{case}: request count')
    previous=0
    for row,event in zip(rows,events):
        require(all(row.get(k)==v for k,v in event.items()),f'{case}: request/trace mismatch')
        require(all(isinstance(row[k],(int,float)) and math.isfinite(row[k]) and row[k]>=0
                    for k in ['seconds','response_seconds','issued_s','completed_s']),f'{case}: invalid request time')
        require(previous<=row['issued_s']<=row['completed_s']<=result['job_wall_s'],f'{case}: request ordering')
        require(row['seconds']<=row['response_seconds']+1e-6 and
                row['response_seconds']<=row['completed_s']-row['issued_s']+1e-6,f'{case}: response interval')
        previous=row['completed_s']
        require(row['sha256']==expected[str(row['key'])] if verify_content else row['sha256'] is None,
                f'{case}: content SHA or speed/hash separation')
    total=sum(e['bytes'] for e in events)
    require(total==result['logical_bytes']==metrics.get('read_bytes'),f'{case}: logical bytes')
    require(result['job_wall_s']>0 and result['completed_with_background_s']>=result['job_wall_s'],f'{case}: wall/drain')
    require(result['effective_mib_s']==total/MIB/result['job_wall_s'],f'{case}: actual throughput')
    require(result['request_p99_s']==percentile([r['response_seconds'] for r in rows],.99),f'{case}: p99')
    require(result['request_p50_s']==percentile([r['response_seconds'] for r in rows],.5),f'{case}: p50')
    access,durable=archived_sql(case)
    require(durable==metrics and result['metrics_snapshot']=='after_daemon_shutdown',f'{case}: SQL metric receipt')
    counts=collections.Counter((f"/gpu0/shard-{e['key']:06d}.tokens",e['caller']) for e in events)
    require(access==dict(counts),f'{case}: SQL access counts')
    require(metrics.get('read_open_count')==len(events),f'{case}: open accounting')
    require(metrics.get('read_release_count')==len(events),f'{case}: release fence accounting')
    require(sum(metrics.get('read_'+t+'_bytes',0) for t in ['remote','local','inflight'])==total,f'{case}: tier accounting')
    for tier in ['remote','local','inflight']:
        require(metrics.get('request_cost_'+tier+'_samples',0)==metrics.get(tier+'_read_open_count',0) and
                metrics.get('request_cost_'+tier+'_bytes',0)==metrics.get('read_'+tier+'_bytes',0),f'{case}: request cost')
    require(not any(v for k,v in metrics.items() if k.endswith('error_count')),f'{case}: native errors')
    require(metrics.get('background_submitted',0)==metrics.get('background_completed',0),f'{case}: incomplete background')
    require(metrics.get('read_fill_buffer_peak_bytes',0)<=4*MIB,f'{case}: retained capture budget')
    require(len(result['retained_cache_bytes'])==len(config['gpus']) and
            all(n<=g['local_quota_mib']*MIB for n,g in zip(result['retained_cache_bytes'],config['gpus'])),f'{case}: disk quotas')
    physical_ops=metrics.get('direct_backend_pread_ops',0);physical_bytes=metrics.get('direct_backend_pread_bytes',0)
    hits=metrics.get('direct_read_tail_hits',0);hit_bytes=metrics.get('direct_read_tail_bytes',0)
    disk_ops=sum(metrics.get('read_'+t+'_ops',0) for t in ['local','remote'])
    disk_bytes=sum(metrics.get('read_'+t+'_bytes',0) for t in ['local','remote'])
    require(physical_ops+hits==disk_ops and physical_bytes>=disk_bytes,f'{case}: physical vs logical I/O')
    tail_peak=metrics.get('direct_read_tail_buffer_bytes_peak',0)
    tail_enabled=config['policy']['reuse_direct_read_tail']
    if tail_enabled:
        created=metrics.get('direct_read_tail_buffers_created',0)
        require(created==sum(metrics.get(t+'_read_open_count',0) for t in ['local','remote']),f'{case}: tail allocations')
        require(tail_peak%4096==0 and tail_peak<=created*4096 and hit_bytes<=hits*4096,f'{case}: separate tail payload budget')
    else:
        require(hits==hit_bytes==tail_peak==metrics.get('direct_read_tail_buffers_created',0)==0,f'{case}: disabled tail active')
    return result

def build_pairs(cases):
    pairs=[];aggregates=[]
    for block,arms in sorted(cases.items()):
        scene=block.rsplit('-',2)[0]
        for treatment,baseline in PAIRS:
            x=arms[treatment];y=arms[baseline]
            gain=(y['job_wall_s']/x['job_wall_s']-1)*100
            reduction=(1-x['request_p99_s']/y['request_p99_s'])*100
            pairs.append(dict(block=block,scene=scene,treatment=treatment,baseline=baseline,
              treatment_mib_s=x['effective_mib_s'],baseline_mib_s=y['effective_mib_s'],
              throughput_gain_pct=gain,treatment_p99_ms=x['request_p99_s']*1000,
              baseline_p99_ms=y['request_p99_s']*1000,p99_reduction_pct=reduction,
              both_improved=gain>0 and reduction>0,
              drain_gain_pct=(y['completed_with_background_s']/x['completed_with_background_s']-1)*100))
    for scene in sorted({p['scene'] for p in pairs}):
        for treatment,baseline in PAIRS:
            selected=[p for p in pairs if p['scene']==scene and p['treatment']==treatment and p['baseline']==baseline]
            x=[cases[p['block']][treatment] for p in selected];y=[cases[p['block']][baseline] for p in selected]
            xt=sum(r['logical_bytes'] for r in x)/MIB/math.fsum(r['job_wall_s'] for r in x)
            yt=sum(r['logical_bytes'] for r in y)/MIB/math.fsum(r['job_wall_s'] for r in y)
            xp=statistics.median(r['request_p99_s'] for r in x)*1000
            yp=statistics.median(r['request_p99_s'] for r in y)*1000
            aggregates.append(dict(scene=scene,treatment=treatment,baseline=baseline,
              treatment_mib_s=xt,baseline_mib_s=yt,throughput_gain_pct=(xt/yt-1)*100,
              treatment_p99_ms=xp,baseline_p99_ms=yp,p99_reduction_pct=(1-xp/yp)*100,
              both_improved_rounds=sum(p['both_improved'] for p in selected),rounds=len(selected)))
    return pairs,aggregates

def mechanisms(cases,study):
    rows=[]
    for block,arms in sorted(cases.items()):
        for name,r in arms.items():
            m=r['metrics']
            policy_events=read(Path(study.audit_root)/block/name/'policy-events.json')
            requests=read(Path(study.audit_root)/block/name/'requests.json')
            seen=set();first_access=set()
            for index,request in enumerate(requests):
                if request['key'] not in seen:first_access.add(index)
                seen.add(request['key'])
            tail_count=math.ceil(len(requests)*.01)
            tail_indices=set(sorted(range(len(requests)),key=lambda i:requests[i]['response_seconds'])[-tail_count:])
            rows.append(dict(block=block,scene=block.rsplit('-',2)[0],strategy=name,
              throughput_mib_s=r['effective_mib_s'],p99_ms=r['request_p99_s']*1000,
              physical_pread_ops=m.get('direct_backend_pread_ops',0),physical_pread_bytes=m.get('direct_backend_pread_bytes',0),
              tail_hits=m.get('direct_read_tail_hits',0),tail_hit_bytes=m.get('direct_read_tail_bytes',0),
              tail_payload_peak_bytes=m.get('direct_read_tail_buffer_bytes_peak',0),
              capture_peak_bytes=m.get('read_fill_buffer_peak_bytes',0),
              completed_copies=sum(e['action'] in ['PROMOTE_READY','REPLICATE_READY','REPLICA_READY'] for e in policy_events),
              background_tasks=m.get('background_completed',0),
              request_cost_mean_us={tier:m.get('request_cost_'+tier+'_us',0)/max(1,m.get('request_cost_'+tier+'_samples',0))
                                    for tier in ['local','remote','inflight']},
              first_access_requests=len(first_access),slowest_one_percent_requests=tail_count,
              first_access_in_slowest_one_percent=len(first_access & tail_indices),
              remote_bytes=m.get('read_remote_bytes',0),local_bytes=m.get('read_local_bytes',0),
              ram_bytes=m.get('read_inflight_bytes',0),daemon_cpu_s=r['daemon_cpu_s'],
              **study.mechanism(Path(study.audit_root)/block/name)))
    return rows

def validate_acceptance(pairs,aggregates,mechanism_rows,source_pairs):
    by_mechanism={(r['block'],r['strategy']):r for r in mechanism_rows}
    source={(r['block'],r['baseline']):r for r in source_pairs}
    for pair in pairs:
        identity=(pair['block'],pair['baseline']);record=source[identity]
        x=by_mechanism[(pair['block'],pair['treatment'])];y=by_mechanism[identity]
        changed=x['action_sha256']!=y['action_sha256']
        active=changed if pair['baseline'] not in ['PoolSIEVE1','SyncSubmission'] else True
        if pair['baseline']=='NoAffinity':active=active and x['relocated']>0 and y['relocated']==0
        if pair['baseline']=='NoJoint':active=active and x['admissions_with_displacement']>0
        passed=(pair['both_improved'] and pair['drain_gain_pct']>=0 and active and
                (pair['baseline'] in ['PoolSIEVE1','SyncSubmission'] or changed))
        require(record['gain_pct']==pair['throughput_gain_pct'] and
                record['p99_change_pct']==-pair['p99_reduction_pct'] and
                record['drain_gain_pct']==pair['drain_gain_pct'],'paired metrics disagree with frozen source')
        require(record['mechanism_active']==active and record['executed_actions_changed']==changed and
                record['pilot_screen']==passed,'strict acceptance disagrees with frozen source')
        pair.update(mechanism_active=active,executed_actions_changed=changed,
                    full_acceptance=passed,primary_comparison=(pair['treatment'],pair['baseline']) in PRIMARY_PAIRS)
    for row in aggregates:
        selected=[p for p in pairs if p['scene']==row['scene'] and
                  p['treatment']==row['treatment'] and p['baseline']==row['baseline']]
        row['full_acceptance_rounds']=sum(p['full_acceptance'] for p in selected)
        row['all_rounds_passed']=all(p['full_acceptance'] for p in selected)

def verify(evidence,source,output,freeze_path=None):
    evidence=Path(evidence).resolve();source=Path(source).resolve();output=Path(output).resolve()
    require(output!=evidence and evidence not in output.parents,'output must be outside immutable evidence')
    freeze_path=Path(freeze_path).resolve() if freeze_path else evidence/'provenance/freeze.json'
    freeze=read(freeze_path);before=tree_hashes(evidence)
    sqlite_preservation=verify_sqlite_preservation(evidence)
    require((evidence/'development').is_dir() and (evidence/'correctness').is_dir(),'--evidence must directly contain development/ and correctness/')
    require(not list(evidence.rglob('failure.json')),'failed run receipt present')
    for name in ['development.exit','correctness.exit']:
        require((evidence/name).read_text().strip()=='0',name+' not successful')
    with tempfile.TemporaryDirectory(prefix='tokenfs-submission-fence78-review-') as temp:
        temp=Path(temp).resolve();src=temp/'source';src.mkdir();extract_source(source,src)
        for name in freeze['source_hashes']:
            require(not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe source freeze path')
        require({str(p.relative_to(src)) for p in src.rglob('*') if p.is_file()}==set(freeze['source_hashes']),
                'source archive has extra or missing files')
        actual={p:sha(src/p) for p in freeze['source_hashes']}
        require(actual==freeze['source_hashes'],'source freeze differs from archive')
        sys.path.insert(0,str(src/'scripts'))
        study=importlib.import_module('submission_fence_hpj_study')
        require(Path(study.__file__).resolve().is_relative_to(src),'wrong imported study')
        require(set(study.SOURCES)==set(actual),'source set differs from freeze')
        require(sha(src/'study-configs/submission-fence-development.json')==freeze['specs']['development'],'spec freeze')
        diagnostic=importlib.import_module('tail_diagnostic_analysis');diagnostic.read_access_metrics=archived_sql
        data=temp/'evidence';shutil.copytree(evidence,data)
        speed=data/'development';study.audit_root=str(speed)
        manifest=read(speed/'manifest.json')
        require(manifest['source_hashes']==actual and manifest['binary_sha256']==freeze['binary_sha256'],'speed source/binary freeze')
        require(manifest['verify'] is False and manifest['backend_direct'] is True,'timing mode changed')
        require(manifest['spec']==study.expected_spec(),'speed matrix changed')
        old_summary=read(speed/'summary.json');old_comparisons=read(speed/'comparisons.json')
        audit=study.audit(speed);require(audit['passed'] and audit['checked_runs']==24,'frozen source audit failed: '+str(audit))
        with contextlib.redirect_stdout(io.StringIO()):study.report(speed)
        require(old_summary==read(speed/'summary.json') and old_comparisons==read(speed/'comparisons.json'),'source report recomputation differs')
        cases={};object_cache={};last_finished=0
        for block in manifest['spec']['blocks']:
            path=speed/block['id'];trace=study.trace(block);require(read(path/'trace.json')==trace,'speed trace changed')
            key=(block['scenario'],block['seed'])
            if key not in object_cache:object_cache[key]=expected_objects(block,trace)
            expected=object_cache[key];require(read(path/'objects.json')==expected,'speed input SHA changed')
            for name in study.arm_order(block):
                environment=read(path/name/'environment.json')
                before_ns=environment['before']['monotonic_ns'];after_ns=environment['after']['monotonic_ns']
                require(last_finished<=before_ns<=after_ns,'execution order/overlap differs from frozen order')
                last_finished=after_ns
            cases[block['id']]={}
            for name in study.VARIANTS:
                case=path/name;cfg=study.configuration(name,Path(manifest['output'])/block['id']/name,Path(manifest['remote_data'])/block['id'],24,True)
                cases[block['id']][name]=verify_rows(case,trace,expected,cfg,freeze['binary_sha256'],False)
        content=data/'correctness';cm=read(content/'manifest.json');ca=read(content/'audit.json')
        require(cm['source_hashes']==actual and cm['binary_sha256']==freeze['binary_sha256'],'content source/binary freeze')
        require(cm['study']=='submission_fence_hpj_study' and cm['stage']=='content_correctness_not_speed' and cm['variants']==study.VARIANTS,'content study mismatch')
        require(cm['driver_sha256']==sha(src/'scripts/disk_opportunity_correctness.py'),'content driver changed')
        require(ca['passed'] and ca['cases']==6 and ca['requests']==576,'content audit receipt')
        require({p.parent.name for p in content.glob('*/result.json')}==set(study.VARIANTS),'extra or missing correctness case')
        spec=dict(id='content-check',scenario='moving_shared',seed=3401,requests=96,shard_mib=2,quota_mib=24)
        require(cm['spec']==spec,'content matrix changed');events=study.trace(spec)
        require(read(content/'trace.json')==events and len(events)==96,'content trace changed')
        expected=expected_objects(spec,events);require(read(content/'objects.json')==expected,'content input SHA changed')
        for name in study.VARIANTS:
            cfg=study.configuration(name,Path(cm['output'])/name,Path(cm['remote_data']),24,True)
            verify_rows(content/name,events,expected,cfg,freeze['binary_sha256'],True)
        pairs,aggregates=build_pairs(cases);mechanism_rows=mechanisms(cases,study)
        validate_acceptance(pairs,aggregates,mechanism_rows,old_comparisons)
        binaries=list((evidence/'provenance').glob('tokenfs'))
        for binary in binaries:require(sha(binary)==freeze['binary_sha256'],'archived binary differs')
        require(tree_hashes(evidence)==before,'raw evidence mutated during review')
        review=dict(passed=True,study='submission_fence_hpj_study',source_files=len(actual),
          source_archive_sha256=sha(source),binary_sha256=freeze['binary_sha256'],binary_receipts_verified=30,
          binary_file_verified=bool(binaries),speed_runs=24,speed_requests=27648,
          correctness_runs=6,content_checks=576,source_report_exact=True,
          input_payload_hashes_reproduced=True,sql_metrics_and_access_exact=True,raw_evidence_unchanged=True,
          sqlite_preservation=sqlite_preservation,reverse_run_order_verified=True,
          paired_comparisons=len(pairs),aggregate_comparisons=len(aggregates),
          interpretation='Frozen HPJ/SIEVE development comparisons on two inspected inputs, two reversed-order rounds; SyncSubmission is a separate foreground telemetry diagnostic, not a fourth policy innovation or independent confirmation.',
          p99_aggregation='median of two per-run nearest-rank p99 values; not pooled request p99',
          throughput_aggregation='sum logical bytes / sum full foreground wall seconds',
          ram_accounting='tail payload is additional to retained capture budget; tail metric excludes C++ object metadata',
          strict_both_improved_primary=sum(p['both_improved'] for p in pairs if (p['treatment'],p['baseline']) in PRIMARY_PAIRS),
          strict_both_improved_sync_submission=sum(p['both_improved'] for p in pairs if p['baseline']=='SyncSubmission'),
          acceptance_criterion='throughput gain > 0; p99 reduction > 0; drain gain >= 0; active mechanism; changed actions for component ablations',
          full_acceptance_primary=sum(p['full_acceptance'] for p in pairs if p['primary_comparison']),
          primary_comparisons=16,primary_all_passed=all(p['full_acceptance'] for p in pairs if p['primary_comparison']),
          full_acceptance_sync_submission=sum(p['full_acceptance'] for p in pairs if p['baseline']=='SyncSubmission'))
    output.mkdir(parents=True,exist_ok=True)
    dump(output/'review.json',review);dump(output/'pairs.json',pairs);dump(output/'aggregates.json',aggregates)
    dump(output/'mechanisms.json',mechanism_rows);dump(output/'evidence-hashes.json',before)
    dump(output/'strict-primary.json',dict(passed=review['primary_all_passed'],passing_comparisons=review['full_acceptance_primary'],
                                         comparisons=16,pairs=[p for p in pairs if p['primary_comparison']]))
    header=['|负载|吞吐(完整/对照 MiB/s)|吞吐变化%|p99(完整/对照 ms)|p99降低%|双指标改善|完整验收|',
            '|---|---:|---:|---:|---:|---:|---:|']
    lines=['# Frozen HPJ four tables','',
      '吞吐为两轮总字节/总时间；p99为两轮各自p99的中位数。正的吞吐变化、p99降低率表示改善。完整验收另含drain不退化、机制触发及消融动作变化；不以汇总均值代替逐轮验收。逻辑GPU域开发验证，不是独立确认。','',
      f"主比较完整验收：{review['full_acceptance_primary']}/16；{'全部通过' if review['primary_all_passed'] else '尚未全部通过'}。",'']
    labels=['热点估值消融：Full / NoHotspot','亲和放置消融：Full / NoAffinity',
            '联合决策消融：Full / NoJoint','整体比较：Full / PoolSIEVE1']
    def format_rows(selected):
        return [f"|{r['scene']}|{r['treatment_mib_s']:.3f} / {r['baseline_mib_s']:.3f}|{r['throughput_gain_pct']:+.3f}|{r['treatment_p99_ms']:.3f} / {r['baseline_p99_ms']:.3f}|{r['p99_reduction_pct']:+.3f}|{r['both_improved_rounds']}/{r['rounds']}|{r['full_acceptance_rounds']}/{r['rounds']}|" for r in selected]
    for label,pair in zip(labels,PRIMARY_PAIRS):
        lines+=['## '+label,'']+header+format_rows([r for r in aggregates if (r['treatment'],r['baseline'])==pair])+['']
    (output/'four-tables.md').write_text('\n'.join(lines)+'\n')
    appendix=['# Submission-telemetry diagnostic: Full / SyncSubmission','',
              'Same policy; only synchronous versus fenced background submission telemetry differs. This diagnostic is separate from the four primary policy tables.','']+header+format_rows([r for r in aggregates if r['baseline']=='SyncSubmission'])
    (output/'sync-submission-diagnostic.md').write_text('\n'.join(appendix)+'\n')
    return review

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ['evidence','source','output']:parser.add_argument('--'+arg,type=Path,required=True)
    parser.add_argument('--freeze',type=Path)
    args=parser.parse_args()
    try:
        result=verify(args.evidence,args.source,args.output,args.freeze)
    except Exception as exc:
        failure=dict(passed=False,error=str(exc))
        destination=args.output.resolve();raw=args.evidence.resolve()
        if destination!=raw and raw not in destination.parents:
            destination.mkdir(parents=True,exist_ok=True);dump(destination/'review.json',failure)
        print(json.dumps(failure,ensure_ascii=False),file=sys.stderr);raise
    print(json.dumps(result,ensure_ascii=False))
