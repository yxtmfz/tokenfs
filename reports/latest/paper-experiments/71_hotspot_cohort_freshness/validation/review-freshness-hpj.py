import sys,json,math,hashlib,sqlite3,statistics,tempfile,shutil,random
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parent;tag=sys.argv[1] if len(sys.argv)>1 else 'integrated-hpj';source=root/(tag+'-source');data=root/(tag+'-data')
sys.path.insert(0,str(source/'scripts'))
study=__import__(tag.replace('-','_')+'_study')
from evidence_benchmark import percentile
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=load(data/'provenance/freeze.json');batchroot=data/'development';m=load(batchroot/'manifest.json')
assert freeze['source_hashes']==m['source_hashes'] and freeze['binary_sha256']==m['binary_sha256']
for p,h in freeze['source_hashes'].items():assert sha(source/p)==h,p
assert sha(source/('study-configs/'+tag+'-development.json'))==freeze['specs']['development']
assert m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(',')
# Closed, checkpointed archive only: never use immutable against a live WAL.
# Cross-check all durable counters against captured JSON below; this also
# rejects an archive whose missing WAL contained any audited observations.
import tail_diagnostic_analysis as diagnostic
from contextlib import closing
def archive_access_metrics(case):
 assert not list(Path(case).glob('state.db-*'))
 with closing(sqlite3.connect((Path(case)/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
  return ({(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')},dict(db.execute('SELECT name,value FROM metrics')))
diagnostic.read_access_metrics=archive_access_metrics
batch=study.audit(batchroot);assert batch['passed'] and batch['checked_runs']==sum(len(b['variants']) for b in m['spec']['blocks'])
rs={};mechanisms=[];metric_discrepancies=[]
for b in m['spec']['blocks']:
 expected=load(batchroot/b['id']/'objects.json')
 for key,h in expected.items():
  payload=random.Random(b['seed']*100000+int(key)).randbytes(study.MIB)
  assert hashlib.sha256(payload*b['shard_mib']).hexdigest()==h
 for v in b['variants']:
  case=batchroot/b['id']/v;r=load(case/'result.json');rows=load(case/'requests.json');cfg=load(case/'config.json');metrics=r['metrics'];rs[b['id'],v]=r
  assert (case/'request-trace.json').exists()==bool(cfg['policy'].get('request_trace_path'))
  assert r['request_p99_s']==percentile([x['response_seconds'] for x in rows],.99)
  assert all(0<=x['seconds']<=x['response_seconds']<=x['completed_s']-x['issued_s']+1e-9 for x in rows)
  assert metrics.get('legacy_affinity_statistics_skipped')==len(rows)
  if 'caller' in tag:
   assert metrics.get('affinity_cross_gpu_caller_count',0)==sum(x['caller']!=0 for x in rows)
   assert metrics.get('affinity_caller_env_invalid',0)==metrics.get('affinity_caller_env_unreadable',0)==0
  counts=Counter((f"/gpu0/shard-{x['key']:06d}.tokens",x['caller']) for x in rows)
  orders={(f"/gpu0/shard-{x['key']:06d}.tokens",x['caller']):x['index']+1 for x in rows}
  with sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
   assert {(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}==dict(counts)
   assert {(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,access_order FROM gpu_access')}==orders
   assert db.execute('SELECT COUNT(*) FROM gpu_access_events').fetchone()[0]==0
   assert dict(db.execute('SELECT name,value FROM metrics'))==metrics
  assert r['metrics_snapshot']=='after_daemon_shutdown'
  for tier in ['local','remote','inflight']:
   assert metrics.get('request_cost_'+tier+'_samples',0)==metrics.get(tier+'_read_open_count',0)
   assert metrics.get('request_cost_'+tier+'_bytes',0)==metrics.get('read_'+tier+'_bytes',0)
   if metrics.get('request_cost_'+tier+'_samples',0):assert 0<metrics.get('request_cost_'+tier+'_us',0)<=metrics.get('read_'+tier+'_latency_us_total',0)
   else:assert metrics.get('request_cost_'+tier+'_us',0)==0
  assert cfg['policy']['coalesce_pending_reads'] is True
  assert cfg['policy']['retain_read_fill'] is True
  assert cfg['policy']['capture_local_reads'] is True
  assert cfg['policy']['bounded_cost_warmup'] is True
  assert cfg['policy']['batch_policy_events'] is True
  if any(x in tag for x in ['exactverify','cohort','writepath']):
   assert metrics.get('read_fill_exact_verify_count',0)==metrics.get('read_fill_copy_count',0)
  if 'cohort' in tag:
   assert cfg['policy']['cohort_reuse_prior']==(v!='PoolSIEVE1')
   if 'calibrated' in tag:assert cfg['policy']['recent_value_floor']==(v!='PoolSIEVE1')
   if v in ['NoHotspot','PoolSIEVE1']:assert metrics.get('measured_cohort_prior_plans',0)==0
  assert metrics.get('local_capture_started',0)>=0
  assert metrics.get('local_capture_started',0)+metrics.get('local_capture_unavailable',0)==metrics.get('local_read_open_count',0)
  assert metrics.get('retained_capture_hit',0)==metrics.get('inflight_read_open_count',0)
  assert cfg['policy']['efficient_measured_planning']==(v!='PoolSIEVE1')
  assert cfg['policy']['burst_interval_survival']==(v!='PoolSIEVE1')
  assert cfg['policy']['reuse_scaled_exploration']==(v!='PoolSIEVE1')
  assert cfg['policy']['persistent_run_reuse']==(v!='PoolSIEVE1')
  assert cfg['policy']['persistent_reuse_immediate_decay']==(v!='PoolSIEVE1')
  if v in ['NoHotspot','NoAffinity','NoJoint']:
   full=load(batchroot/b['id']/'Full'/'config.json')['policy']
   flag={'NoHotspot':'measured_static_reuse_value','NoAffinity':'shared_caller_only','NoJoint':'measured_joint_admission'}[v]
   assert {k for k in full if k!='request_trace_path' and full[k]!=cfg['policy'][k]}=={flag}
  if cfg['policy'].get('measured_policy',False):
   assert metrics.get('copy_cost_full_us',0)==sum(metrics.get(k,0) for k in ['copy_cost_remaining_us','copy_cost_planning_us','copy_cost_capture_us'])
   assert metrics.get('copy_cost_charged_us',0)==metrics.get('copy_cost_remaining_us' if cfg['policy'].get('incremental_copy_cost',False) else 'copy_cost_full_us',0)
   if metrics.get('copy_cost_samples',0):assert metrics['copy_cost_remaining_us']>0 and metrics['copy_cost_planning_us']>0
  assert sum(metrics.get(t+'_read_open_count',0) for t in ['local','remote','inflight'])==len(rows)
  assert sum(metrics.get('read_'+t+'_bytes',0) for t in ['local','remote','inflight'])==r['logical_bytes']
  assert metrics.get('inflight_capture_borrowed',0)==metrics.get('inflight_read_open_count',0)
  if not cfg['policy']['coalesce_pending_reads']:assert metrics.get('read_inflight_bytes',0)==0
  events=load(case/'policy-events.json');commits=[e for e in events if e['action'] in ['PROMOTE_READY','REPLICATE_READY']]
  copies=sum(metrics.get(k,0) for k in ['promote_count','cross_gpu_replica_create_count'])
  copybytes=sum(metrics.get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])
  if cfg['policy'].get('measured_policy',False):assert metrics.get('copy_cost_samples',0)==copies
  assert len(commits)==copies and copybytes==copies*b['shard_mib']*study.MIB
  fill=cfg['policy']['foreground_read_fill'];n=metrics.get('read_fill_copy_count',0)
  if fill:
   assert 0<metrics.get('read_fill_buffer_peak_bytes',0)<=cfg['policy']['read_fill_buffer_bytes']
   assert metrics.get('read_fill_capture_started',0)+metrics.get('read_fill_capture_unavailable',0)==metrics['remote_read_open_count']+metrics.get('local_capture_started',0)+metrics.get('local_capture_unavailable',0)
   assert metrics.get('read_fill_capture_complete',0)<=metrics['read_fill_capture_started']
   assert metrics.get('read_fill_capture_bytes',0)==metrics.get('read_fill_capture_complete',0)*b['shard_mib']*study.MIB
   assert 0<=n<=copies and metrics.get('read_fill_copy_bytes',0)==n*b['shard_mib']*study.MIB<=metrics.get('read_fill_capture_bytes',0)
   assert (metrics.get('read_fill_committed_capture_us',0)>0)==(n>0)
  else:assert not any(value for k,value in metrics.items() if k.startswith('read_fill_'))
  if v.startswith('PoolSIEVE'):assert r['retained_cache_bytes'][1:]==[0,0]
  mechanisms.append(dict(block=b['id'],seed=b['seed'],repeat=b['repeat'],strategy=v,copy_count=copies,reused_copy_count=n,
   source_copy_count=copies-n,inflight_bytes=metrics.get('read_inflight_bytes',0),inflight_opens=metrics.get('inflight_read_open_count',0),remote_bytes=metrics.get('read_remote_bytes',0),local_bytes=metrics.get('read_local_bytes',0),rss_kib=r['daemon_peak_rss_kib'],staging_peak_bytes=metrics.get('read_fill_buffer_peak_bytes',0),
   capture_us=metrics.get('read_fill_capture_us',0),committed_capture_us=metrics.get('read_fill_committed_capture_us',0),
   capture_complete=metrics.get('read_fill_capture_complete',0),capture_unavailable=metrics.get('read_fill_capture_unavailable',0)))

summary=load(batchroot/'summary.json');pairs=load(batchroot/'comparisons.json')
assert len(summary)==batch['checked_runs'] and len(pairs)==sum(len(b['variants'])-1 for b in m['spec']['blocks'])
by_block={b['id']:b for b in m['spec']['blocks']}
mechs={}
for row in summary:
 b=by_block[row['block']];v=row['strategy'];r=rs[b['id'],v]
 fns=dict(mib_s=lambda r:r['logical_bytes']/study.MIB/r['job_wall_s'],cpu_s=lambda r:r['daemon_cpu_s'],
  p99_ms=lambda r:r['request_p99_s']*1000,drain_mib_s=lambda r:r['logical_bytes']/study.MIB/r['completed_with_background_s'],
  remote_mib=lambda r:r['metrics'].get('read_remote_bytes',0)/study.MIB,inflight_mib=lambda r:r['metrics'].get('read_inflight_bytes',0)/study.MIB)
 for k,f in fns.items():assert math.isclose(row[k],f(r),rel_tol=1e-12,abs_tol=1e-12),(b['id'],v,k)
 events=load(batchroot/b['id']/v/'policy-events.json');pending={};relocated=0;selected=0;places=0;loss_admits=0;actions=[]
 for e in events:
  fields=dict(t.split('=',1) for t in e['reason'].split(';') if '=' in t)
  identity=(e['logical_path'],e['gpu_id'])
  if e['action']=='SHARED_PLACE':
   places+=1;selected+=int(fields['caller'])!=e['gpu_id'];pending[identity]=int(fields['caller'])
  if e['action']=='ADMIT':loss_admits+=float(fields.get('displaced',0))+float(fields.get('uncertainty',0))>0
  if e['action'] in ['PROMOTE_READY','REPLICATE_READY','REPLICA_READY'] and identity in pending:
   relocated+=pending.pop(identity)!=e['gpu_id']
  if e['action'] in ['PROMOTE_READY','REPLICATE_READY','REPLICA_READY','EVICT']:actions.append((e['action'],*identity))
 h=hashlib.sha256(json.dumps(actions,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 expected=dict(action_sha256=h,placements=places,selected_relocations=selected,relocated=relocated,admissions_with_displacement=loss_admits)
 for k,val in expected.items():assert row[k]==val,(b['id'],v,k)
 if v=='NoAffinity':assert selected==relocated==0
 mechs[b['id'],v]=expected
for p in pairs:
 b=by_block[p['block']];x=rs[b['id'],'Full'];y=rs[b['id'],p['baseline']]
 assert p['seed']==b['seed'] and p['scenario']==b['scenario'] and p['n']==1 and p['treatment']=='Full'
 gain=(y['job_wall_s']/x['job_wall_s']-1)*100;tail=(x['request_p99_s']/y['request_p99_s']-1)*100
 assert math.isclose(p['gain_pct'],gain,abs_tol=1e-10)
 assert math.isclose(p['p99_change_pct'],tail,abs_tol=1e-10)
 assert math.isclose(p['drain_gain_pct'],(y['completed_with_background_s']/x['completed_with_background_s']-1)*100,abs_tol=1e-10)
 changed=mechs[b['id'],'Full']['action_sha256']!=mechs[b['id'],p['baseline']]['action_sha256']
 active=changed if p['baseline']!='PoolSIEVE1' else True
 if p['baseline']=='NoAffinity':active=active and mechs[b['id'],'Full']['relocated']>0 and mechs[b['id'],p['baseline']]['relocated']==0
 if p['baseline']=='NoJoint':active=active and mechs[b['id'],'Full']['admissions_with_displacement']>0
 assert p['executed_actions_changed']==changed and p['mechanism_active']==active
 strict=any(x in tag for x in ['atomic','fence','caller'])
 assert p['acceptance_version']==('strict-dual-metric-v3' if strict else 'positive-throughput-v2')
 assert p['pilot_screen']==bool(gain>0 and (tail<0 if strict else tail<=0) and p['drain_gain_pct']>=0 and active and (changed or p['baseline']=='PoolSIEVE1'))

last=0
for b in m['spec']['blocks']:
 for v in study.arm_order(b):
  env=load(batchroot/b['id']/v/'environment.json')
  assert last<=env['before']['monotonic_ns']<env['after']['monotonic_ns']
  last=env['after']['monotonic_ns']
for seed in sorted({b['seed'] for b in m['spec']['blocks']}):
 bb=[b for b in m['spec']['blocks'] if b['seed']==seed]
 assert len({sha(batchroot/b['id']/'trace.json') for b in bb})==1
 assert len({sha(batchroot/b['id']/'objects.json') for b in bb})==1
 assert len(bb)==2 and study.arm_order(bb[0])==study.arm_order(bb[1])[::-1]
rollup=[]
for scene,seed in dict.fromkeys((b['scenario'],b['seed']) for b in m['spec']['blocks']):
 bb=[b for b in m['spec']['blocks'] if b['seed']==seed]
 for v in bb[0]['variants']:
  rr=[rs[b['id'],v] for b in bb]
  ev=[]
  for b in bb:
   events=load(batchroot/b['id']/v/'policy-events.json')
   # Only stationary labels are unambiguous for this offline mechanism audit.
   ev.append(sum(e['action']=='EVICT' and int(e['logical_path'].split('shard-')[1].split('.')[0])<8 for e in events) if scene=='stationary_shared' else None)
  rollup.append(dict(scenario=scene,seed=seed,strategy=v,n=len(rr),rates=[r['effective_mib_s'] for r in rr],mean_mib_s=statistics.mean(r['effective_mib_s'] for r in rr),hot_evictions=ev,
    copies=[sum(r['metrics'].get(k,0) for k in ['promote_count','cross_gpu_replica_create_count']) for r in rr],
    adjusted_plans=[r['metrics'].get('measured_persistent_reuse_plans',0) for r in rr]))
instrumented=any(load(batchroot/b['id']/v/'config.json')['policy']['profile_control_path'] for b in m['spec']['blocks'] for v in b['variants'])
assert not instrumented and m['spec']==study.expected_spec()
assert len(m['spec']['blocks'])==4 and batch['checked_runs']==12
expected_pairs={(b['id'],v) for b in m['spec']['blocks'] for v in b['variants'][1:]}
assert {(p['block'],p['baseline']) for p in pairs}==expected_pairs and len(pairs)==len(expected_pairs)
build_lines=(root/(tag+'-build.json')).read_text().splitlines()
build_freeze=next(json.loads(line) for line in reversed(build_lines) if line.startswith('{"source_hashes"'))
assert freeze==build_freeze
assert m['reference_binary_sha256']=='b09253aa1577e6104421b797641b8952bd151c988eb3d9bef562b82d210cde37'
for b in m['spec']['blocks']:
 for v in b['variants']:
  expected_binary=m['reference_binary_sha256'] if v=='OldFull' else freeze['binary_sha256']
  assert load(batchroot/b['id']/v/'execution.json')==dict(binary_sha256=expected_binary)
for b in m['spec']['blocks']:
 assert b['seed'] not in [3293,3401]
 if b['scenario']=='public_toolagent':
  events=load(batchroot/b['id']/'trace.json')
  assert all(e['caller']==e['source_request']%3 for e in events)

pruning=[]
for b in m['spec']['blocks']:
 for v in b['variants']:
  metrics=rs[b['id'],v]['metrics']
  avoided=metrics.get('shared_snapshot_avoided',0);rejected=metrics.get('shared_optimistic_rejects',0)
  assert 0<=avoided<=rejected
  if v=='PoolSIEVE1':assert avoided==rejected==0
  pruning.append(dict(block=b['id'],variant=v,snapshots_avoided=avoided,locations_pruned=rejected,snapshots=metrics.get('compact_planning_snapshots',0)))
# A legitimate input may offer no prunable work; report that as inactive, not corrupt data.
result=dict(pruning=pruning,passed=True,speed_evidence=not instrumented,source_files_verified=len(freeze['source_hashes']),batch=batch,
 requests=sum(len(load(batchroot/b['id']/v/'requests.json')) for b in m['spec']['blocks'] for v in b['variants']),
 mechanisms=mechanisms,pairs=pairs,rollup=rollup,all_gates_passed=not instrumented and all(p['pilot_screen'] for p in pairs),
 limits='H-only development, report70 inputs reused, two reversed-order repeats and exact report70 binary control; P/J/SIEVE not revalidated')
(root/(tag+'-review.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
