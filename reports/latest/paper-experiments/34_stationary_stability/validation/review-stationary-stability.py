import sys,json,math,hashlib,sqlite3,statistics,tempfile,shutil,random
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parent;source=root/'stationary-stability-source';data=root/'stationary-stability-data'
sys.path.insert(0,str(source/'scripts'))
import stationary_stability_study as study
from evidence_benchmark import percentile
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=load(data/'provenance/freeze.json');batchroot=data/'development';m=load(batchroot/'manifest.json')
assert freeze['source_hashes']==m['source_hashes'] and freeze['binary_sha256']==m['binary_sha256']
for p,h in freeze['source_hashes'].items():assert sha(source/p)==h,p
assert sha(source/'study-configs/stationary-stability-development.json')==freeze['specs']['development']
assert m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(',')
batch=study.audit(batchroot);assert batch['passed'] and batch['checked_runs']==18
rs={};mechanisms=[];metric_discrepancies=[]
for b in m['spec']['blocks']:
 expected=load(batchroot/b['id']/'objects.json')
 for key,h in expected.items():
  payload=random.Random(b['seed']*100000+int(key)).randbytes(study.MIB)
  assert hashlib.sha256(payload*b['shard_mib']).hexdigest()==h
 for v in b['variants']:
  case=batchroot/b['id']/v;r=load(case/'result.json');rows=load(case/'requests.json');cfg=load(case/'config.json');metrics=r['metrics'];rs[b['id'],v]=r
  assert not cfg['policy']['profile_control_path'] and not cfg['policy'].get('request_trace_path')
  assert not (case/'request-trace.json').exists()
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
  assert cfg['policy']['reuse_scaled_exploration']==(v=='Full')
  if v=='BurstFull':
   full=load(batchroot/b['id']/'Full'/'config.json')['policy']
   assert {k for k in full if full[k]!=cfg['policy'][k]}=={'reuse_scaled_exploration'}
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
assert len(summary)==18 and len(pairs)==12
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
 active=changed if p['baseline']=='BurstFull' else True
 assert p['executed_actions_changed']==changed and p['mechanism_active']==active
 assert p['acceptance_version']=='positive-throughput-v2'
 assert p['pilot_screen']==bool(gain>0 and tail<=0 and p['drain_gain_pct']>=0 and active and (changed or p['baseline']=='PoolSIEVE1'))
reuse=load(data/'provenance/binary-reuse.json')
assert reuse['recompiled'] is False
assert reuse['original_freeze']['binary_sha256']==m['binary_sha256']=='2757459e304a99751ed9f9c69b3a549c56243dbeb3b779f29cb68ce9164a591c'
for p,h in reuse['original_freeze']['source_hashes'].items():assert freeze['source_hashes'][p]==h
last=0
for b in m['spec']['blocks']:
 for v in study.arm_order(b):
  env=load(batchroot/b['id']/v/'environment.json')
  assert last<=env['before']['monotonic_ns']<env['after']['monotonic_ns']
  last=env['after']['monotonic_ns']
for seed in [3271,3291]:
 blocks=[b for b in m['spec']['blocks'] if b['seed']==seed]
 assert len(blocks)==3
 for v in study.VARIANTS:assert sorted(study.arm_order(b).index(v) for b in blocks)==[0,1,2]
 assert len({sha(batchroot/b['id']/'trace.json') for b in blocks})==1
 assert len({sha(batchroot/b['id']/'objects.json') for b in blocks})==1
stable=load(batchroot/'stability.json');assert len(stable)==4
# Independent df2 quantile from the closed-form CDF; unit is an entire run.
tcrit=math.sqrt(2)*.95/math.sqrt(1-.95*.95)
for q in stable:
 bb=[b for b in m['spec']['blocks'] if b['seed']==q['seed']]
 xs=[rs[b['id'],'Full'] for b in bb];ys=[rs[b['id'],q['baseline']] for b in bb]
 logs=[math.log(y['job_wall_s']/x['job_wall_s']) for x,y in zip(xs,ys)]
 mean=sum(logs)/3;se=math.sqrt(sum((v-mean)**2 for v in logs)/2/3)
 limits=[100*math.expm1(mean-tcrit*se),100*math.expm1(mean+tcrit*se)]
 assert all(math.isclose(a,b,abs_tol=1e-10) for a,b in zip(limits,q['paired_log_t95_pct']))
 assert math.isclose(q['paired_gain_geo_pct'],100*math.expm1(mean),abs_tol=1e-10)
 speed=sum(y['job_wall_s']>x['job_wall_s'] for x,y in zip(xs,ys))
 tail=sum(x['request_p99_s']<=y['request_p99_s'] for x,y in zip(xs,ys))
 drain=sum(x['completed_with_background_s']<=y['completed_with_background_s'] for x,y in zip(xs,ys))
 assert (q['speed_wins'],q['p99_nonregressions'],q['drain_nonregressions'])==(speed,tail,drain)
 assert q['repeat_consistent']==(speed==tail==drain==3)
 assert q['stability_screen']==(speed==tail==drain==3 and limits[0]>0)
 selected=[p for p in pairs if p['seed']==q['seed'] and p['baseline']==q['baseline']]
 assert q['action_changed_pairs']==sum(p['executed_actions_changed'] for p in selected)
 for key,expected in dict(min_gain_pct=min(p['gain_pct'] for p in selected),max_gain_pct=max(p['gain_pct'] for p in selected),worst_p99_change_pct=max(p['p99_change_pct'] for p in selected),min_drain_gain_pct=min(p['drain_gain_pct'] for p in selected)).items():assert math.isclose(q[key],expected,abs_tol=1e-10)
 for arm,rr in [('Full',xs),(q['baseline'],ys)]:
  rates=[x['logical_bytes']/study.MIB/x['job_wall_s'] for x in rr];a=q['strategies'][arm]
  want=dict(mean_mib_s=statistics.mean(rates),min_mib_s=min(rates),max_mib_s=max(rates),cv_pct=statistics.stdev(rates)/statistics.mean(rates)*100,p99_min_ms=min(x['request_p99_s']*1000 for x in rr),p99_max_ms=max(x['request_p99_s']*1000 for x in rr))
  for k,v in want.items():assert math.isclose(a[k],v,abs_tol=1e-10)
eviction_evidence=[]
for b in m['spec']['blocks']:
 events=load(batchroot/b['id']/'Full'/'policy-events.json');admitted={}
 for e in events:
  if e['action']=='ADMIT':admitted[e['gpu_id']]=e
  if e['action']=='EVICT' and int(e['logical_path'].split('shard-')[1].split('.')[0])<8:
   a=admitted[e['gpu_id']];assert a['seq']<e['seq'] and a['bytes']==e['bytes']==2*study.MIB
   f=dict(v.split('=',1) for v in a['reason'].split(';') if '=' in v)
   eviction_evidence.append(dict(block=b['id'],evict_seq=e['seq'],admit_seq=a['seq'],location=e['gpu_id'],hot_key=e['logical_path'],incoming=a['logical_path'],incoming_is_scan=int(a['logical_path'].split('shard-')[1].split('.')[0])>=64,estimated_displaced_us=float(f['displaced']),estimated_incoming_us=float(f['incoming']),estimated_copy_us=float(f['copy'])))
result=dict(passed=True,source_files_verified=len(freeze['source_hashes']),batch=batch,
 requests=sum(len(load(batchroot/b['id']/v/'requests.json')) for b in m['spec']['blocks'] for v in b['variants']),
 mechanisms=mechanisms,pairs=pairs,eviction_evidence=eviction_evidence,stability=stable,all_stability_screens_passed=all(q['stability_screen'] for q in stable),all_gates_passed=all(p['pilot_screen'] for p in pairs),
 limits='18 balanced repeats, n3 per seed/arm, same prior executable; no new seeds or physical GPU measurement; exploratory parametric intervals with unverified assumptions')
(root/'stationary-stability-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
