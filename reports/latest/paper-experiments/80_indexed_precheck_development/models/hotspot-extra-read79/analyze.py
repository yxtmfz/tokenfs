from pathlib import Path
import collections,csv,hashlib,itertools,json,re,subprocess,shutil
R=Path(__file__).resolve().parent
E=R.parent/'hotspot-precheck79/evidence/development'
load=lambda p:json.loads(p.read_text())
rows=lambda p:list(csv.DictReader(p.open(),delimiter='\t'))
logs={a:rows(R/f'{a}-model.tsv') for a in ['Full','NoHotspot','PoolSIEVE1']}
reqs={a:{int(x['observation']):x for x in rr if x['kind']=='request'} for a,rr in logs.items()}
rem={a:{i for i,x in rr.items() if x['detail']=='0:0'} for a,rr in reqs.items()}
probes=rows(R/'past-only-probes.tsv')
assert [x for x in rows(R/'probe-actions.tsv') if x['arm']=='Full']==logs['Full']
assert [x for x in rows(R/'probe-actions.tsv') if x['arm']=='NoHotspot']==logs['NoHotspot']
assert rem['Full']==rem['NoHotspot']
q=reqs['Full'];first={};last={}
for i,row in q.items():first.setdefault(row['key'],i);last[row['key']]=i
assert len(first)==67
counts={a:{'remote':len(rem[a]),'disk':sum(x['detail']=='0:1' for x in rr.values()),'ram':sum(x['detail'].startswith('1:') for x in rr.values()),'copies':sum(x['kind']=='copy' for x in logs[a])} for a,rr in reqs.items()}
for c in counts.values():c['fixed_cost_ms']=21*c['remote']+10.5*c['disk']+8*c['copies'];assert c['remote']+c['disk']+c['ram']==1152
actual=[];hashes={}
for round in [1,2]:
 for arm in logs:
  case=E/f'moving_shared-74801-r{round}'/arm
  for name in ['requests.json','policy-events.json','result.json','config.json']:hashes[str(case/name)]=hashlib.sha256((case/name).read_bytes()).hexdigest()
  requests=load(case/'requests.json');events=load(case/'policy-events.json');result=load(case/'result.json')
  assert all(str(row['key'])==q[row['index']+1]['key'] for row in requests)
  copies=[(int(re.search(r'shard-(\d+)',x['logical_path']).group(1)),x['gpu_id']) for x in events if x['action'] in ['PROMOTE_READY','REPLICATE_READY']]
  modeled=[(int(x['key']),int(x['detail'].split(':')[0])) for x in logs[arm] if x['kind']=='copy']
  assert [k for k,g in copies]==[k for k,g in modeled]
  m=result['metrics'];assert m['remote_read_open_count']==counts[arm]['remote'] and m['inflight_read_open_count']==counts[arm]['ram']
  actual.append({'round':round,'arm':arm,'remote_count':m['remote_read_open_count'],'ram_count':m['inflight_read_open_count'],'copy_key_sequence_identical':True,'copy_key_domain_sequence_identical':copies==modeled,'domain_difference':[(j,x,y) for j,(x,y) in enumerate(zip(modeled,copies)) if x!=y]})

def probes_at(arm,key,i,moment):
 values=[x for x in probes if x['arm']==arm and x['key']==key and int(x['observation'])==i and x['moment']==moment]
 def norm(p):return {k:(int(v) if k in ['observation','domain','allowed','frequency'] else float(v) if k in ['incoming','displaced','uncertainty','copy','cohort'] else v) for k,v in p.items()}
 return [norm(x) for x in values]

def best(values):
 if not values:return None
 return max(values,key=lambda x:x['incoming']-x['displaced']-x['uncertainty']-x['copy'])
extra=[]
for i in sorted(rem['Full']-rem['PoolSIEVE1']):
 key=q[i]['key'];history=[x for j,x in q.items() if j<i]
 starts=[int(list(group)[0]['observation']) for k,group in itertools.groupby(history,key=lambda x:x['key']) if k==key]
 prev=max(j for j in q if j<i and q[j]['key']==key)
 ev=max(int(x['observation']) for x in logs['Full'] if x['kind']=='ram_evict' and x['key']==key and int(x['observation'])<i)
 copied=max(int(x['observation']) for x in logs['PoolSIEVE1'] if x['kind']=='copy' and x['key']==key and int(x['observation'])<i)
 report={'index':i-1,'observation':i,'key':int(key),'prior_run_starts':starts,'previous_access_observation':prev,'previous_run_start':starts[-1],'distance_from_previous_access':i-prev,'distance_from_previous_run_start':i-starts[-1],'ram_eviction_observation':ev,'since_RAM_eviction':i-ev,'sieve_prior_copy_observation':copied,'earlier_forecast':{}}
 for arm in ['Full','NoHotspot']:
  ps=probes_at(arm,key,prev,'current_observed');pe=probes_at(arm,key,ev,'RAM_eviction')
  eligible=sorted({int(x['observation']) for x in probes if x['arm']==arm and x['key']==key and x['moment']=='current_observed' and x['allowed']=='1' and int(x['observation'])<i})
  report['earlier_forecast'][arm]={'previous_last_request':ps,'at_RAM_eviction':pe,'earliest_prior_current_observation_allowed':eligible[0] if eligible else None,'earliest_allowed_request_route_in_model':reqs[arm][eligible[0]]['detail'] if eligible else None}
 extra.append(report)
reverse=[]
for i in sorted(rem['PoolSIEVE1']-rem['Full']):
 key=q[i]['key'];evictions=[(int(x['observation']),x['key']) for x in logs['PoolSIEVE1'] if x['kind']=='copy' and key in x['detail'].split(':')[1:] and int(x['observation'])<i]
 reverse.append({'index':i-1,'observation':i,'key':int(key),'sieve_previous_eviction':evictions[-1] if evictions else None})
assert len(extra)==16 and len(reverse)==9
assert {x['key'] for x in extra}==set(range(8,24))
assert sum(len(x['prior_run_starts'])==1 for x in extra)==14
allowed=[x['key'] for x in extra if x['earlier_forecast']['Full']['earliest_prior_current_observation_allowed'] is not None]
assert allowed==[12,21,17]
result={'model_not_recorded_request_routes':True,'observations_are_1_based_indices_are_0_based':True,'compulsory_first_objects':67,'model_counts':counts,'actual_reproduction':actual,'full_only_remote':extra,'sieve_only_remote':reverse,'net_extra_remote':7,'earlier_profitable_captures_full_and_NoH':[12,21,17],'no_future_decision_input':True,'source_evidence_hashes':hashes,'limits':['79 requests contain no source tier, and policy events have no observation or timestamp. Matching READY sequences and aggregate source counts does not prove the modeled exact request-to-tier mapping.','Native original estimators use fixedcosts and instantaneous copies; past-only probe calls inspect but do not change decisions or count as performance.','Counterfactual earlier copy could evict another useful resident or consume pinned buffer capacity; do not subtract target misses while assuming other actions stay fixed.']}
(R/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['|Request index (0-based)|Object|Previous run start / last access (1-based)|RAM eviction (1-based)|Gap since previous run start|Earlier original Full / NoH admission possible?|','|---:|---:|---:|---:|---:|---|']
for x in extra:
 def answer(arm):
  i=x['earlier_forecast'][arm]['earliest_prior_current_observation_allowed'];return str(i) if i else 'no'
 lines.append(f"|{x['index']}|{x['key']}|{x['previous_run_start']} / {x['previous_access_observation']}|{x['ram_eviction_observation']}|{x['distance_from_previous_run_start']}|{answer('Full')} / {answer('NoHotspot')}|")
(R/'extra-table.md').write_text('\n'.join(lines)+'\n')
# Actual evidence unchanged by analysis.
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in hashes.items())
print(json.dumps({'counts':counts,'extra':len(extra),'reverse':len(reverse),'earlier_allowed':allowed,'actual_counts_and_READY_key_sequences_reproduced':True},indent=2))
