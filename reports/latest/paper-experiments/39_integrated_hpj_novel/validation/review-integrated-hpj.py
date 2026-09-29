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
  assert metrics.get('legacy_affinity_statistics_skipped')==len(rows)
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
  assert cfg['policy']['efficient_measured_planning']==(v!='PoolSIEVE1')
  assert cfg['policy']['burst_interval_survival']==(v!='PoolSIEVE1')
  assert cfg['policy']['reuse_scaled_exploration']==(v!='PoolSIEVE1')
  assert cfg['policy']['persistent_run_reuse']==(v!='PoolSIEVE1')
  assert cfg['policy']['persistent_reuse_immediate_decay']==(v!='PoolSIEVE1')
  if v in ['StaticValue','CallerOnly','Independent']:
   full=load(batchroot/b['id']/'Full'/'config.json')['policy']
   flag={'StaticValue':'measured_static_reuse_value','CallerOnly':'shared_caller_only','Independent':'measured_joint_admission'}[v]
   assert {k for k in full if k!='request_trace_path' and full[k]!=cfg['policy'][k]}=={flag}
  if cfg['policy'].get('measured_policy',False):
   assert metrics['copy_cost_full_us']==metrics['copy_cost_remaining_us']+metrics['copy_cost_planning_us']+metrics['copy_cost_capture_us']
   assert metrics['copy_cost_charged_us']==metrics['copy_cost_remaining_us' if cfg['policy'].get('incremental_copy_cost',False) else 'copy_cost_full_us']
   assert metrics['copy_cost_remaining_us']>0 and metrics['copy_cost_planning_us']>0
  assert sum(metrics.get(t+'_read_open_count',0) for t in ['local','remote','inflight'])==len(rows)
  assert sum(metrics.get('read_'+t+'_bytes',0) for t in ['local','remote','inflight'])==r['logical_bytes']
  assert metrics.get('inflight_capture_borrowed',0)==metrics.get('inflight_read_open_count',0)
  if not cfg['policy']['coalesce_pending_reads']:assert metrics.get('read_inflight_bytes',0)==0
  events=load(case/'policy-events.json');commits=[e for e in events if e['action'] in ['PROMOTE_READY','REPLICATE_READY']]
  copies=sum(metrics.get(k,0) for k in ['promote_count','cross_gpu_replica_create_count'])
  copybytes=sum(metrics.get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])
  if cfg['policy'].get('measured_policy',False):assert metrics['copy_cost_samples']==copies
  assert len(commits)==copies and copybytes==copies*b['shard_mib']*study.MIB
  fill=cfg['policy']['foreground_read_fill'];n=metrics.get('read_fill_copy_count',0)
  if fill:
   assert 0<metrics.get('read_fill_buffer_peak_bytes',0)<=cfg['policy']['read_fill_buffer_bytes']
   assert metrics.get('read_fill_capture_started',0)+metrics.get('read_fill_capture_unavailable',0)==metrics['remote_read_open_count']
   assert metrics.get('read_fill_capture_complete',0)<=metrics['read_fill_capture_started']
   assert metrics.get('read_fill_capture_bytes',0)==metrics.get('read_fill_capture_complete',0)*b['shard_mib']*study.MIB
   assert 0<n<=copies and metrics['read_fill_copy_bytes']==n*b['shard_mib']*study.MIB<=metrics['read_fill_capture_bytes']
   assert metrics.get('read_fill_committed_capture_us',0)>0
  else:assert not any(value for k,value in metrics.items() if k.startswith('read_fill_'))
  if v.startswith('PoolSIEVE'):assert r['retained_cache_bytes'][1:]==[0,0]
  mechanisms.append(dict(block=b['id'],seed=b['seed'],repeat=b['repeat'],strategy=v,copy_count=copies,reused_copy_count=n,
   source_copy_count=copies-n,inflight_bytes=metrics.get('read_inflight_bytes',0),inflight_opens=metrics.get('inflight_read_open_count',0),remote_bytes=metrics.get('read_remote_bytes',0),local_bytes=metrics.get('read_local_bytes',0),rss_kib=r['daemon_peak_rss_kib'],staging_peak_bytes=metrics.get('read_fill_buffer_peak_bytes',0),
   capture_us=metrics.get('read_fill_capture_us',0),committed_capture_us=metrics.get('read_fill_committed_capture_us',0),
   capture_complete=metrics.get('read_fill_capture_complete',0),capture_unavailable=metrics.get('read_fill_capture_unavailable',0)))

summary=load(batchroot/'summary.json');pairs=load(batchroot/'comparisons.json')
assert len(summary)==batch['checked_runs'] and len(pairs)==len(m['spec']['blocks'])*4
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
 if v=='CallerOnly':assert selected==relocated==0
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
 if p['baseline']=='CallerOnly':active=active and mechs[b['id'],'Full']['relocated']>0 and mechs[b['id'],p['baseline']]['relocated']==0
 if p['baseline']=='Independent':active=active and mechs[b['id'],'Full']['admissions_with_displacement']>0
 assert p['executed_actions_changed']==changed and p['mechanism_active']==active
 assert p['acceptance_version']=='positive-throughput-v2'
 assert p['pilot_screen']==bool(gain>0 and tail<=0 and p['drain_gain_pct']>=0 and active and (changed or p['baseline']=='PoolSIEVE1'))

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
rollup=[]
for scene,seed in [('stationary_shared',3271),('moving_shared',3293),('uniform',3273)]:
 bb=[b for b in m['spec']['blocks'] if b['seed']==seed]
 for v in study.VARIANTS:
  rr=[rs[b['id'],v] for b in bb]
  ev=[]
  for b in bb:
   events=load(batchroot/b['id']/v/'policy-events.json')
   # Only stationary labels are unambiguous for this offline mechanism audit.
   ev.append(sum(e['action']=='EVICT' and int(e['logical_path'].split('shard-')[1].split('.')[0])<8 for e in events) if scene=='stationary_shared' else None)
  rollup.append(dict(scenario=scene,seed=seed,strategy=v,n=len(rr),rates=[r['effective_mib_s'] for r in rr],mean_mib_s=statistics.mean(r['effective_mib_s'] for r in rr),hot_evictions=ev,
    copies=[sum(r['metrics'].get(k,0) for k in ['promote_count','cross_gpu_replica_create_count']) for r in rr],
    adjusted_plans=[r['metrics'].get('measured_persistent_reuse_plans',0) for r in rr]))
result=dict(passed=True,source_files_verified=len(freeze['source_hashes']),batch=batch,
 requests=sum(len(load(batchroot/b['id']/v/'requests.json')) for b in m['spec']['blocks'] for v in b['variants']),
 mechanisms=mechanisms,pairs=pairs,rollup=rollup,all_gates_passed=all(p['pilot_screen'] for p in pairs),
 limits='integrated frozen development matrix, known inputs; no statistical confirmation or physical GPUs')
(root/(tag+'-review.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
