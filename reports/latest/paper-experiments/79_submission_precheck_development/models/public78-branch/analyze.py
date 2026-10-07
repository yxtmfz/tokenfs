from pathlib import Path
import json,math,collections,hashlib
root=Path(__file__).resolve().parent;raw=root.parents[1]/'hotspot-submission78/evidence/development'
rows=[];forecast0=64/14;forecast1=forecast0*2**(-1/14);noise=1+math.sqrt(2)
for rnd in [1,2]:
 for arm in ['Full','SyncSubmission','NoHotspot']:
  case=raw/f'public_toolagent-74802-r{rnd}'/arm
  events=json.loads((case/'policy-events.json').read_text());result=json.loads((case/'result.json').read_text());requests=json.loads((case/'requests.json').read_text())
  def fields(e):return {k:float(v) for k,v in (x.split('=',1) for x in e['reason'].split(';') if '=' in x)}
  selected=[]
  for e in events:
   key=int(e['logical_path'].split('shard-')[-1].split('.')[0])
   if e['action'] in ['SHARED_PLACE','ADMIT'] and 45<=key<=56:
    f=fields(e)
    x={'seq':e['seq'],'action':e['action'],'key':key,'score':e['score'],'fields':f}
    if f['incoming']<22000 and f.get('explore',0)==0:
     x['inferred_saving_us_if_second_visit_victim_count1']=f['uncertainty']/noise
     x['dimensionless_forecast_ratio']=f['incoming']/(f['uncertainty']/noise)
     if e['action']=='SHARED_PLACE':
      x['counterfactual_one_observation_decay_margin_us']=e['score']-f['incoming']*(1-2**(-1/14))
    selected.append(x)
  m=result['metrics'];firstdup=[];seen=set()
  for q in requests[:70]:
   if q['key'] in seen:firstdup.append({k:q[k] for k in ['index','key','caller','seconds','response_seconds']})
   seen.add(q['key'])
  rows.append({'round':rnd,'arm':arm,'remote':m['remote_read_open_count'],'local':m['local_read_open_count'],'ready_actions':sum(e['action'] in ['PROMOTE_READY','REPLICATE_READY'] for e in events),'action_counts':dict(collections.Counter(e['action'] for e in events)),'commit_rejects':{k:v for k,v in m.items() if k.startswith('measured_commit_')},'early_duplicate_requests':firstdup,'events45_56':selected,'aggregate_cost_metrics':{k:v for k,v in m.items() if k.startswith('request_cost_') or k.startswith('copy_cost_')},'input_hashes':{n:hashlib.sha256((case/n).read_bytes()).hexdigest() for n in ['requests.json','policy-events.json','result.json']}})
out={'source_version':78,'not_real_cost_replay':True,'definition':'Algebraic decomposition of printed observed event fields plus original78 fixed-prefix forecast component replay. Event logs lack per-sample rates, observation clock, timestamps and rejection details. Counterfactual one-observation margins hold cost/state fixed; they are evidence of sensitivity, not reconstructed rejected decisions.','second_visit_initial_forecast':forecast0,'one_observation_later_forecast':forecast1,'uncertainty_factor_for_one_count1_victim':noise,'rows':rows}
(root/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
for r in rows:
 first=next((e for e in r['events45_56'] if e['action']=='ADMIT'),None)
 print(r['round'],r['arm'],'remote',r['remote'],'READY',r['ready_actions'],'first',first)
