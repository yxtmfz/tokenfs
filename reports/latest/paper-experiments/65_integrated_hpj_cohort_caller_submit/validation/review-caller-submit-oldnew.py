from pathlib import Path
from collections import Counter
from contextlib import closing
import json,hashlib,sqlite3,sys,math,random
root=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-caller-submit'
source=root/(tag+'-source');data=root/(tag+'-data')/'oldnew'
sys.path.insert(0,str(source/'scripts'))
import integrated_hpj_cohort_caller_submit_study as study
from evidence_benchmark import percentile
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=load(data/'manifest.json');assert m['order']==['old','new','new','old']
assert m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(',')
for name,v in m['versions'].items():
 src=root/(v['tag']+'-source')
 for p,h in v['freeze']['source_hashes'].items():assert sha(src/p)==h
 ref=load(root/(v['tag']+'-data')/'provenance/freeze.json')
 assert v['freeze']==ref
trace=study.trace(m['spec']);assert trace==load(data/'trace.json') and len(trace)==576
expected=load(data/'objects.json')
for key,h in expected.items():assert hashlib.sha256(random.Random(m['spec']['seed']*100000+int(key)).randbytes(study.MIB)*2).hexdigest()==h
rs=[];summary=[];last=0
for i,name in enumerate(m['order']):
 case=data/f'{i+1}-{name}';r=load(case/'result.json');rows=load(case/'requests.json');cfg=load(case/'config.json');metrics=r['metrics']
 assert cfg==study.configuration('Full',Path(m['output'])/case.name,Path(m['remote_data']),24,True)
 assert not (case/'request-trace.json').exists() and not cfg['policy'].get('profile_control_path')
 assert len(rows)==576 and all(all(row[k]==value for k,value in e.items()) for row,e in zip(rows,trace))
 assert r['status']=='ok' and r['strategy']=='Full' and not r['verify_every_request']
 assert r['logical_bytes']==sum(e['bytes'] for e in trace)==metrics['read_bytes']
 assert r['metrics_snapshot']=='after_daemon_shutdown' and metrics['read_open_count']==576
 assert r['request_p99_s']==percentile([x['response_seconds'] for x in rows],.99)
 assert math.isclose(r['effective_mib_s'],r['logical_bytes']/study.MIB/r['job_wall_s'],rel_tol=1e-12)
 prior=0
 for row in rows:
  assert prior<=row['issued_s']<=row['completed_s']<=r['job_wall_s'];prior=row['completed_s']
  # response and completed use consecutive clock reads, not one timestamp.
  assert 0<=row['seconds']<=row['response_seconds']<=row['completed_s']-row['issued_s']+1e-9
 assert metrics['background_submitted']==metrics['background_completed']
 assert not any(v for k,v in metrics.items() if k.endswith('error_count'))
 assert metrics['affinity_cross_gpu_caller_count']==sum(e['caller']!=0 for e in trace)
 assert metrics.get('affinity_caller_env_invalid',0)==metrics.get('affinity_caller_env_unreadable',0)==0
 assert metrics['read_fill_buffer_peak_bytes']<=4*study.MIB
 assert sum(r['retained_cache_bytes'])<=24*study.MIB
 assert metrics['read_fill_exact_verify_count']==metrics['read_fill_copy_count']>0
 assert sum(metrics.get('read_'+t+'_bytes',0) for t in ['remote','local','inflight'])==r['logical_bytes']
 assert not list(case.glob('state.db-*'))
 with closing(sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
  assert dict(db.execute('SELECT name,value FROM metrics'))==metrics
  assert {(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}==dict(Counter((f"/gpu0/shard-{e['key']:06d}.tokens",e['caller']) for e in trace))
 env=load(case/'environment.json');assert last<env['before']['monotonic_ns']<env['after']['monotonic_ns'];last=env['after']['monotonic_ns']
 rs.append(r);summary.append(dict(index=i+1,version=name,mib_s=r['effective_mib_s'],p99_ms=r['request_p99_s']*1000))
assert summary==load(data/'summary.json')
pairs=[]
for old,new in [(0,1),(3,2)]:
 a,b=rs[old],rs[new]
 pairs.append(dict(old_case=old+1,new_case=new+1,old_p99_ms=a['request_p99_s']*1000,new_p99_ms=b['request_p99_s']*1000,p99_reduction_pct=(1-b['request_p99_s']/a['request_p99_s'])*100,throughput_gain_pct=(b['effective_mib_s']/a['effective_mib_s']-1)*100))
out=dict(passed=True,runs=4,requests=2304,order=m['order'],summary=summary,comparisons=pairs,both_metrics_improve_both_orders=all(p['p99_reduction_pct']>0 and p['throughput_gain_pct']>0 for p in pairs),statistical_confirmation=False)
(root/'caller-submit-oldnew-review.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
