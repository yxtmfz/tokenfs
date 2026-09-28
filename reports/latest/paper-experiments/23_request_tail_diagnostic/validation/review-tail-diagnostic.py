import sys,json,hashlib,sqlite3,statistics,math,shutil,tempfile,copy
from pathlib import Path
from collections import Counter
root=Path(__file__).resolve().parent
source=root/'tail-diagnostic-source';data=root/'tail-diagnostic-data'
sys.path.insert(0,str(source/'scripts'))
import tail_diagnostic_study as study
from tail_diagnostic_analysis import analyze_case,intersection_ns
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=load(data/'provenance/freeze.json');manifest=load(data/'diagnostic/manifest.json')
assert freeze['source_hashes']==manifest['source_hashes']
assert freeze['binary_sha256']==manifest['binary_sha256']
for p,h in freeze['source_hashes'].items():assert sha(source/p)==h,p
assert sha(source/'study-configs/tail-diagnostic.json')==freeze['specs']['diagnostic']
assert manifest['nvme_identity']['transport']=='tcp'
assert 'traddr=28.10.10.13' in manifest['nvme_identity']['address'].split(',')
batch=study.audit(data/'diagnostic');assert batch['passed'] and batch['checked_runs']==6
rows=[];expanded=[]
for b in manifest['spec']['blocks']:
 for arm in b['variants']:
  case=data/'diagnostic'/b['id']/arm
  d=analyze_case(case);d.update(seed=b['seed'],strategy=arm)
  assert d==load(case/'diagnosis.json')
  rows.append(d)
  events=load(case/'request-trace.json')['events'];client=load(case/'requests.json')
  details=[]
  for r,original in zip(client,d['request_details']):
   path=f"/gpu0/shard-{r['key']:06d}.tokens"
   attrs=[e for e in events if e['op']=='getattr' and e['path']==path and r['start_ns']<=e['start_ns']<=e['end_ns']<=r['opened_ns']]
   previous=[(e['start_ns'],e['end_ns']) for e in events if e['op']=='release' and e['handle']!=original['handle']]
   extra=dict(getattr_ms=sum(e['end_ns']-e['start_ns'] for e in attrs)/1e6,
      getattr_wait_ms=sum(e['wait_ns'] for e in attrs)/1e6,
      prior_release_overlap_open_ms=intersection_ns(r['start_ns'],r['opened_ns'],previous)/1e6)
   details.append(dict(original,**extra))
  slow=sorted(details,key=lambda r:r['response_ms'],reverse=True)[:6]
  orders={(f"/gpu0/shard-{r['key']:06d}.tokens",r['caller']):r['index']+1 for r in client}
  with sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
   assert {(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,access_order FROM gpu_access')}==orders
   assert db.execute('SELECT COUNT(*) FROM gpu_access_events').fetchone()[0]==0
  expanded.append(dict(seed=b['seed'],strategy=arm,slowest=slow,
    extra_all_means={k:statistics.mean(r[k] for r in details) for k in extra},
    extra_tail_means={k:statistics.mean(r[k] for r in slow) for k in extra}))
pairs=[]
for arm in ['PoolSIEVE1','PoolSIEVE2']:
 per=[]
 for seed in [3221,3222]:
  x=next(r for r in rows if r['seed']==seed and r['strategy']=='AdaptiveHP')
  y=next(r for r in rows if r['seed']==seed and r['strategy']==arm)
  per.append(dict(seed=seed,gain_pct=(x['diagnostic_mib_s']/y['diagnostic_mib_s']-1)*100,
    p99_change_pct=(x['p99_ms']/y['p99_ms']-1)*100))
 pairs.append(dict(baseline=arm,per_seed=per,paired_gain_pct=(math.prod(1+p['gain_pct']/100 for p in per)**.5-1)*100))
case=data/'diagnostic/moving_shared-3221/AdaptiveHP';tamper=[]
with tempfile.TemporaryDirectory(prefix='tokenfs-tail-audit-') as tmp:
 t=Path(tmp)
 for p in case.iterdir():
  if p.is_file() and p.name!='request-trace.json':(t/p.name).symlink_to(p.resolve())
 original=load(case/'request-trace.json')
 for mode in ['dropped','wrong_caller','wrong_bytes','negative_interval']:
  value=copy.deepcopy(original)
  if mode=='dropped':value['dropped']=1
  elif mode=='wrong_caller':next(e for e in value['events'] if e['op']=='open')['caller']=99
  elif mode=='wrong_bytes':next(e for e in value['events'] if e['op']=='read')['bytes']+=1
  else:value['events'][0]['end_ns']=0
  (t/'request-trace.json').write_text(json.dumps(value))
  try:analyze_case(t)
  except AssertionError:tamper.append(dict(mutation=mode,rejected=True))
  else:raise AssertionError('accepted corruption '+mode)
result=dict(passed=True,batch=batch,source_files_verified=len(freeze['source_hashes']),
 diagnostic_only=True,all_requests=sum(r['requests'] for r in rows),
 all_events=sum(r['event_count'] for r in rows),dropped=sum(r['dropped'] for r in rows),
 pairs=pairs,tamper_tests=tamper,expanded=expanded)
(root/'tail-diagnostic-review.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='expanded'},indent=2))
