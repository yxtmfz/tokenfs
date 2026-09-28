import sys,json,math,hashlib,sqlite3,statistics,tempfile,shutil
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parent;source=root/'incremental-cost-source';data=root/'incremental-cost-data'
sys.path.insert(0,str(source/'scripts'))
import incremental_cost_study as study
from evidence_benchmark import percentile
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=load(data/'provenance/freeze.json');batchroot=data/'development';m=load(batchroot/'manifest.json')
assert freeze['source_hashes']==m['source_hashes'] and freeze['binary_sha256']==m['binary_sha256']
for p,h in freeze['source_hashes'].items():assert sha(source/p)==h,p
assert sha(source/'study-configs/incremental-cost-development.json')==freeze['specs']['development']
assert m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(',')
batch=study.audit(batchroot);assert batch['passed'] and batch['checked_runs']==12
rs={};mechanisms=[];metric_discrepancies=[]
for b in m['spec']['blocks']:
 for v in b['variants']:
  case=batchroot/b['id']/v;r=load(case/'result.json');rows=load(case/'requests.json');cfg=load(case/'config.json');metrics=r['metrics'];rs[b['seed'],v]=r
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
  for tier in ['local','remote']:
   assert metrics.get('request_cost_'+tier+'_samples',0)==metrics.get(tier+'_read_open_count',0)
   assert metrics.get('request_cost_'+tier+'_bytes',0)==metrics.get('read_'+tier+'_bytes',0)
   assert 0<metrics.get('request_cost_'+tier+'_us',0)<=metrics.get('read_'+tier+'_latency_us_total',0)
  if v=='IncrementalHP':
   oldcfg=load(batchroot/b['id']/'AdaptiveHP'/'config.json')
   # Freeze validation above covers path differences; policy differs in one flag.
   assert oldcfg['policy']['incremental_copy_cost'] is False
   policy=cfg['policy'].copy();policy['incremental_copy_cost']=False
   assert policy==oldcfg['policy']
  if cfg['policy'].get('measured_policy',False):
   assert metrics['copy_cost_full_us']==metrics['copy_cost_remaining_us']+metrics['copy_cost_planning_us']+metrics['copy_cost_capture_us']
   assert metrics['copy_cost_charged_us']==metrics['copy_cost_remaining_us' if cfg['policy']['incremental_copy_cost'] else 'copy_cost_full_us']
   assert metrics['copy_cost_remaining_us']>0 and metrics['copy_cost_planning_us']>0
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
  mechanisms.append(dict(seed=b['seed'],strategy=v,copy_count=copies,reused_copy_count=n,
   source_copy_count=copies-n,staging_peak_bytes=metrics.get('read_fill_buffer_peak_bytes',0),
   capture_us=metrics.get('read_fill_capture_us',0),committed_capture_us=metrics.get('read_fill_committed_capture_us',0),
   capture_complete=metrics.get('read_fill_capture_complete',0),capture_unavailable=metrics.get('read_fill_capture_unavailable',0)))
summary=load(batchroot/'summary.json');pairs=load(batchroot/'comparisons.json')
assert len(summary)==8 and len(pairs)==6
for row in summary:
 values=[rs[b['seed'],row['strategy']] for b in m['spec']['blocks'] if b['scenario']==row['scenario']]
 fns=dict(mib_s=lambda r:r['logical_bytes']/study.MIB/r['job_wall_s'],wall_s=lambda r:r['job_wall_s'],
  cpu_s=lambda r:r['daemon_cpu_s'],p99_ms=lambda r:r['request_p99_s']*1000,
  remote_mib=lambda r:r['metrics'].get('read_remote_bytes',0)/study.MIB,
  copy_mib=lambda r:sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/study.MIB,
  first_read_selections=lambda r:r['metrics'].get('shared_burst_first_read_selected',0),
  forecast_plans=lambda r:r['metrics'].get('measured_burst_forecast_plans',0),
  explorations=lambda r:r['metrics'].get('shared_free_exploration_selected',0),
  uncertainty_plans=lambda r:r['metrics'].get('measured_uncertainty_plans',0),
  open_ms=lambda r:r['metrics'].get('open_control_latency_us_total',0)/r['metrics']['read_open_count']/1000,
  layout_wait_ms=lambda r:r['metrics'].get('open_layout_wait_us',0)/r['metrics']['read_open_count']/1000)
 assert row['n']==len(values)
 for k,f in fns.items():assert math.isclose(row[k],statistics.mean(f(r) for r in values),rel_tol=1e-12,abs_tol=1e-12)
for p in pairs:
 ratios=[]
 for b,per in zip([b for b in m['spec']['blocks'] if b['scenario']==p['scenario']],p['per_seed']):
  x=rs[b['seed'],p['treatment']];y=rs[b['seed'],p['baseline']];ratio=y['job_wall_s']/x['job_wall_s'];ratios.append(ratio)
  assert per['seed']==b['seed']
  assert math.isclose(per['gain_pct'],(ratio-1)*100,abs_tol=1e-10)
  assert math.isclose(per['drain_gain_pct'],(y['completed_with_background_s']/x['completed_with_background_s']-1)*100,abs_tol=1e-10)
  assert math.isclose(per['p99_change_pct'],(x['request_p99_s']/y['request_p99_s']-1)*100,abs_tol=1e-10)
 gain=(math.prod(ratios)**(1/len(ratios))-1)*100
 assert math.isclose(p['paired_gain_pct'],gain,abs_tol=1e-10) and p['wins']==sum(r>1 for r in ratios)
 assert p['pilot_speed_gate']==(gain>=5 and all(r>1 for r in ratios))
 assert p['nonregression_gate']==all(r>=1 for r in ratios)
 assert p['tail_gate']==all(per['p99_change_pct']<=0 for per in p['per_seed'])
result=dict(passed=True,source_files_verified=len(freeze['source_hashes']),batch=batch,
 requests=sum(len(load(batchroot/b['id']/v/'requests.json')) for b in m['spec']['blocks'] for v in b['variants']),
 mechanisms=mechanisms,pairs=pairs,
 all_gates_passed=all((p['pilot_speed_gate'] if p['scenario']=='moving_shared' else p['nonregression_gate']) and p['tail_gate'] for p in pairs if p['baseline'].startswith('PoolSIEVE')),
 limits='twelve development runs: two moving seeds and one uniform seed, four same-binary arms; no latest H/P/J or physical GPU confirmation; exploratory only')
(root/'incremental-cost-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
