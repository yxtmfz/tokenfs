#!/usr/bin/env python3
"""Offline source, raw-I/O, durable-SQL and derived-result review."""
import argparse,json,math,statistics,sqlite3
from pathlib import Path
from collections import Counter
import burst_reuse_study as study
from evidence_benchmark import sha,dump,MIB

def review(data,source,freeze):
 frozen=json.loads(freeze.read_text());errors=[];stages={};mechanisms=[]
 def check(ok,label):
  if not ok:errors.append(label)
 for stage,count in [('correctness',7),('development',18)]:
  root=data/stage;m=json.loads((root/'manifest.json').read_text());a=study.audit(root);stages[stage]=a
  check(a['passed'] and a['checked_runs']==count,stage+': batch count')
  check(m['source_hashes']==frozen['source_hashes'] and m['binary_sha256']==frozen['binary_sha256'],stage+': freeze')
  for p,h in frozen['source_hashes'].items():check(sha(source/p)==h,stage+': source '+p)
  spec=source/f'study-configs/burst-reuse-{stage}.json'
  check(sha(spec)==frozen['specs'][stage] and json.loads(spec.read_text())==m['spec'],stage+': spec')
  if stage=='development':check(m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(','),'NVMe/TCP target')
  for b in m['spec']['blocks']:
   events=study.trace(b);counts=Counter((f"/gpu0/shard-{e['key']:06d}.tokens",e['caller']) for e in events)
   orders={(f"/gpu0/shard-{e['key']:06d}.tokens",e['caller']):e['index']+1 for e in events}
   logical=Counter()
   for (key,gpu),n in counts.items():logical[key]+=n
   for arm in b['variants']:
    c=root/b['id']/arm;r=json.loads((c/'result.json').read_text());metrics=r['metrics'];tag=b['id']+'/'+arm
    check(metrics.get('legacy_affinity_statistics_skipped',0)==b['requests'],tag+': common accounting')
    check(metrics.get('replica_touch_batched',0)==metrics.get('peer_cache_hit',0)+metrics.get('cross_gpu_local_replica_hit',0),tag+': durable touches')
    check(metrics.get('peer_cache_read_bytes',0)==metrics.get('peer_cache_hit',0)*b['shard_mib']*MIB,tag+': peer bytes')
    if arm.startswith('PoolSIEVE'):check(r['retained_cache_bytes'][1:]==[0,0],tag+': shared pool')
    with sqlite3.connect((c/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
     check({(k,g):n for k,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}==dict(counts),tag+': persisted counts')
     check({(k,g):n for k,g,n in db.execute('SELECT logical_path,gpu_id,access_order FROM gpu_access')}==orders,tag+': persisted order')
     check(dict(db.execute('SELECT logical_path,read_count FROM files'))==dict(logical),tag+': object counts')
     check(dict(db.execute('SELECT logical_path,share_count FROM files'))==dict(Counter(k for k,g in counts)),tag+': shares')
     check(db.execute('SELECT COUNT(*) FROM gpu_access_events').fetchone()[0]==0,tag+': no legacy events')
    ev=json.loads((c/'policy-events.json').read_text())
    first=[]
    for e in ev:
     if e['action']=='ADMIT':
      parts=dict(x.split('=',1) for x in e['reason'].split(';')[1:])
      if float(parts.get('burst_remaining',0))>0 and int(parts.get('affinity_count',0))<2:first.append(e)
    if arm!='BurstHP':check(not first and metrics.get('shared_burst_first_read_selected',0)==0,tag+': forecast off')
    elif stage=='development':mechanisms.append(dict(block=b['id'],first_read_selections=metrics.get('shared_burst_first_read_selected',0),committed_first_read_forecasts=len(first),copies=sum(e['action'] in ['PROMOTE_READY','REPLICATE_READY'] for e in ev)))
 root=data/'development';m=json.loads((root/'manifest.json').read_text())
 rows=json.loads((root/'summary.json').read_text());pairs=json.loads((root/'comparisons.json').read_text())
 check(len(rows)==7 and len(pairs)==5,'derived row counts')
 for row in rows:
  bs=[b for b in m['spec']['blocks'] if b['scenario']==row['scenario']]
  vals=[json.loads((root/b['id']/row['strategy']/'result.json').read_text()) for b in bs]
  fns=dict(mib_s=lambda r:r['logical_bytes']/MIB/r['job_wall_s'],wall_s=lambda r:r['job_wall_s'],cpu_s=lambda r:r['daemon_cpu_s'],p99_ms=lambda r:r['request_p99_s']*1000,remote_mib=lambda r:r['metrics'].get('read_remote_bytes',0)/MIB,copy_mib=lambda r:sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB,first_read_selections=lambda r:r['metrics'].get('shared_burst_first_read_selected',0),forecast_plans=lambda r:r['metrics'].get('measured_burst_forecast_plans',0))
  check(row['n']==len(vals),'summary n')
  for k,f in fns.items():check(math.isclose(row[k],statistics.mean(f(r) for r in vals),abs_tol=1e-12,rel_tol=1e-12),row['scenario']+'/'+row['strategy']+': '+k)
 for pair in pairs:
  bs=[b for b in m['spec']['blocks'] if b['scenario']==pair['scenario']];ratios=[]
  check(len(pair['per_seed'])==len(bs)==pair['n'],'paired n')
  for b,per in zip(bs,pair['per_seed']):
   x=json.loads((root/b['id']/'BurstHP'/'result.json').read_text());y=json.loads((root/b['id']/pair['baseline']/'result.json').read_text())
   ratio=y['job_wall_s']/x['job_wall_s'];ratios.append(ratio)
   check(per['seed']==b['seed'] and math.isclose(per['gain_pct'],(ratio-1)*100,abs_tol=1e-10),'paired throughput')
   check(math.isclose(per['drain_gain_pct'],(y['completed_with_background_s']/x['completed_with_background_s']-1)*100,abs_tol=1e-10),'paired drain')
   check(math.isclose(per['p99_change_pct'],(x['request_p99_s']/y['request_p99_s']-1)*100,abs_tol=1e-10),'paired tail')
  gain=(math.prod(ratios)**(1/len(ratios))-1)*100
  check(math.isclose(gain,pair['paired_gain_pct'],abs_tol=1e-10) and pair['wins']==sum(v>1 for v in ratios),'aggregate ratio')
  check(pair['pilot_speed_gate']==(gain>=5 and all(v>1 for v in ratios)),'frozen pilot gate')
 return dict(passed=not errors,errors=errors,stages=stages,mechanisms=mechanisms,interpretation='18 development speed runs, 7 content runs; synthetic logical domains, no significance or physical GPU inference claim; compare both SIEVE admission thresholds')
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in ['data-root','source-root','freeze','output']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();r=review(a.data_root,a.source_root,a.freeze);dump(a.output,r);print(json.dumps(r));raise SystemExit(0 if r['passed'] else 1)
