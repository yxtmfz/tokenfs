#!/usr/bin/env python3
"""Offline review of the bounded H/P factorial; no benchmark execution."""
import argparse,json,math,statistics,sys
from pathlib import Path
import shared_joint_pilot as study
from evidence_benchmark import sha,dump,MIB

def review(data,source,freeze):
 frozen=json.loads(freeze.read_text());errors=[];stages={}
 def check(ok,where):
  if not ok:errors.append(where)
 for stage,count in [('correctness',6),('development',18)]:
  root=data/stage;m=json.loads((root/'manifest.json').read_text());a=study.audit(root);stages[stage]=a
  check(a['passed'] and a['checked_runs']==count,stage+': audit/count')
  check(m['binary_sha256']==frozen['binary_sha256'],stage+': binary')
  check(m['source_hashes']==frozen['source_hashes'],stage+': hashes')
  for name,value in m['source_hashes'].items():check(sha(source/name)==value,stage+': source '+name)
  spec=source/f'study-configs/shared-joint-pilot-{stage}.json'
  check(sha(spec)==frozen['specs'][stage] and json.loads(spec.read_text())==m['spec'],stage+': frozen spec')
  if stage=='development':check(m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(','),stage+': transport')
  for b in m['spec']['blocks']:
   for arm in study.VARIANTS:
    r=json.loads((root/b['id']/arm/'result.json').read_text());metrics=r['metrics']
    check(metrics.get('peer_cache_read_bytes',0)==metrics.get('peer_cache_hit',0)*b['shard_mib']*MIB,b['id']+'/'+arm+': peer bytes')
    if arm=='PoolSIEVE2':check(r['retained_cache_bytes'][1:]==[0,0],b['id']+': pool capacity')
    if arm not in ['P','HP','Independent']:check(metrics.get('shared_placement_selected',0)==0,b['id']+'/'+arm+': P off')
    if arm not in ['H','HP','Independent']:check(metrics.get('measured_shift_resets',0)==0,b['id']+'/'+arm+': H off')
 root=data/'development';m=json.loads((root/'manifest.json').read_text())
 rs={(p.parent.parent.name,p.parent.name):json.loads(p.read_text()) for p in root.glob('*/*/result.json')}
 summaries=json.loads((root/'summary.json').read_text());pairs=json.loads((root/'comparisons.json').read_text());interaction=json.loads((root/'interactions.json').read_text())
 check(len(summaries)==6 and len(pairs)==7,'derived row counts')
 for row in summaries:
  vals=[rs[b['id'],row['strategy']] for b in m['spec']['blocks']]
  fns=dict(mib_s=lambda r:r['logical_bytes']/MIB/r['job_wall_s'],wall_s=lambda r:r['job_wall_s'],cpu_s=lambda r:r['daemon_cpu_s'],p99_ms=lambda r:r['request_p99_s']*1000,remote_mib=lambda r:r['metrics'].get('read_remote_bytes',0)/MIB,copy_mib=lambda r:sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB,peer_mib=lambda r:r['metrics'].get('peer_cache_read_bytes',0)/MIB)
  for field,metric in [('h_resets','measured_shift_resets'),('placements','shared_placement_selected'),('relocated','shared_placement_relocated'),('no_gain','shared_placement_no_gain'),('coalesced','shared_placement_coalesced')]:
   fns[field]=lambda r,k=metric:r['metrics'].get(k,0)
  for k,f in fns.items():check(math.isclose(row[k],statistics.mean(f(r) for r in vals),rel_tol=1e-12,abs_tol=1e-12),row['strategy']+': derived '+k)
 for row in pairs:
  vals=[(rs[b['id'],row['treatment']],rs[b['id'],row['baseline']]) for b in m['spec']['blocks']]
  ratios=[y['job_wall_s']/x['job_wall_s'] for x,y in vals]
  check(math.isclose((math.prod(ratios)**(1/len(vals))-1)*100,row['paired_gain_pct'],abs_tol=1e-10),'paired gain')
  check(row['n']==3 and row['wins']==sum(v>1 for v in ratios),'paired count/wins')
  for b,v,per in zip(m['spec']['blocks'],ratios,row['per_seed']):check(b['seed']==per['seed'] and math.isclose((v-1)*100,per['gain_pct'],abs_tol=1e-10),'per-seed gain')
  drain=(math.prod(y['completed_with_background_s']/x['completed_with_background_s'] for x,y in vals)**(1/len(vals))-1)*100
  check(math.isclose(drain,row['with_drain_gain_pct'],abs_tol=1e-10),'drain gain')
 deltas=[];logs=[]
 for b,row in zip(m['spec']['blocks'],interaction['per_seed']):
  t={n:rs[b['id'],n]['job_wall_s'] for n in study.VARIANTS}
  delta=t['HP']-t['H']-t['P']+t['Shared'];log=math.log(t['HP']*t['Shared']/(t['H']*t['P']))
  deltas.append(delta);logs.append(log)
  check(b['seed']==row['seed'] and math.isclose(delta,row['seconds'],abs_tol=1e-12) and math.isclose(log,row['log_interaction'],abs_tol=1e-12),'interaction per seed')
 check(math.isclose(statistics.mean(deltas),interaction['mean_seconds'],abs_tol=1e-12) and math.isclose(statistics.mean(logs),interaction['mean_log_interaction'],abs_tol=1e-12),'interaction aggregate')
 for arm in study.VARIANTS:
  check({study.arm_order(b).index(arm)//2 for b in m['spec']['blocks']}=={0,1,2},arm+': order balance')
 effects=[]
 for b in m['spec']['blocks']:
  ev={n:json.loads((root/b['id']/n/'policy-events.json').read_text()) for n in study.VARIANTS}
  def actions(n):return [(e['action'],e['logical_path'],e['gpu_id']) for e in ev[n] if e['action'] in ['EVICT','PROMOTE_READY','REPLICATE_READY']]
  charged=0
  for e in ev['HP']:
   if e['action']=='SHARED_PLACE':
    parts=dict(v.split('=',1) for v in e['reason'].split(';'))
    if float(parts['victim_loss'])>0:charged+=1
  effects.append(dict(seed=b['seed'],h_active=rs[b['id'],'HP']['metrics'].get('measured_shift_resets',0)>0,p_active=rs[b['id'],'HP']['metrics'].get('shared_placement_relocated',0)>0,h_actions_differ=actions('HP')!=actions('P'),p_actions_differ=actions('HP')!=actions('H'),j_actions_differ=actions('HP')!=actions('Independent'),selected_plans_with_victim_loss=charged))
 p={(r['treatment'],r['baseline']):r for r in pairs};s={r['strategy']:r for r in summaries}
 def promising(baseline):return p['HP',baseline]['wins']==3 and p['HP',baseline]['paired_gain_pct']>=5
 gates=dict(affinity_conditional_on_H=promising('H') and s['HP']['placements']>0,hotspot_conditional_on_P=promising('P') and s['HP']['h_resets']>0,joint_controller=promising('Independent') and any(e['selected_plans_with_victim_loss']>0 and e['j_actions_differ'] for e in effects),beats_pooled_reference=promising('PoolSIEVE2'))
 return dict(passed=not errors,errors=errors,stages=stages,checked_speed_runs=18,checked_content_runs=6,mechanism_pairs=effects,pilot_gates=gates,mean_interaction_seconds=statistics.mean(deltas),interpretation='exploratory single synthetic scenario; no formal significance, universal superiority, GPU inference or priority-of-invention claim; no automatic expansion')

if __name__=='__main__':
 p=argparse.ArgumentParser()
 for k in ['data-root','source-root','freeze','output']:p.add_argument('--'+k,type=Path,required=True)
 a=p.parse_args();r=review(a.data_root,a.source_root,a.freeze);dump(a.output,r);print(json.dumps(r));sys.exit(0 if r['passed'] else 1)
