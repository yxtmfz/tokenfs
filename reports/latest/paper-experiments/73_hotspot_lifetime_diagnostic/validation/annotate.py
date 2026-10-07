import json,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[1]/'tokenfs-eval'
sys.path.insert(0,str(repo/'scripts'))
from hotspot_lifetime_analysis import analyze_case
root=Path(sys.argv[1]);out={}
for result in sorted(root.glob('*/*/result.json')):
 case=result.parent;r=analyze_case(case)
 trace=json.loads((case/'request-trace.json').read_text())['events']
 opens=sorted([e for e in trace if e['op']=='open' and e['handle']],key=lambda e:e['selected_ns'])
 pending={};ready=[]
 for e in json.loads((case/'policy-events.json').read_text()):
  k=(e['logical_path'],e['gpu_id'])
  if e['action']=='ADMIT':pending[k]=e
  if e['action'] in ['PROMOTE_READY','REPLICATE_READY']:ready.append((k,pending.pop(k,None)))
 assert len(ready)==len(r['lifetimes'])
 for life,(key,admit) in zip(r['lifetimes'],ready):
  assert key==(life['path'],life['location'])
  life['admit']=admit
  if life['end_ns'] is not None:
   future=[e for e in opens if e['path']==life['path'] and e['selected_ns']>=life['end_ns']]
   life['returned_after_eviction']=bool(future)
   life['next_tier']=future[0]['tier'] if future else None
   life['next_after_evict_ms']=(future[0]['selected_ns']-life['end_ns'])/1e6 if future else None
 closed=[r for r in r['lifetimes'] if r['end_ns'] is not None and not r['uncertain']]
 zero=[r for r in closed if not r['disk_reads']]
 r['zero_admission_reasons']={reason:sum(x['admit']['reason'].split(';')[0]==reason for x in zero if x['admit']) for reason in sorted({x['admit']['reason'].split(';')[0] for x in zero if x['admit']})}
 r['zero_returned_after_eviction']=sum(x['returned_after_eviction'] for x in zero)
 r['zero_never_returned']=sum(not x['returned_after_eviction'] for x in zero)
 r['zero_with_cohort_prior']=sum(float(dict(y.split('=',1) for y in x['admit']['reason'].split(';')[1:] if '=' in y).get('cohort_disk_reuse',0))>0 for x in zero if x['admit'])
 out[str(case.relative_to(root))]=r
(root/'annotated-summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:{n:v for n,v in r.items() if n!='lifetimes'} for k,r in out.items()},indent=2))
