import sys,json,hashlib,statistics
from pathlib import Path
root=Path(__file__).resolve().parent;source=root/'readiness-diagnostic-source';data=root/'readiness-diagnostic-data'
sys.path.insert(0,str(source/'scripts'))
import readiness_diagnostic_study as study
from tail_diagnostic_analysis import analyze_case
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
freeze=load(data/'provenance/freeze.json');m=load(data/'diagnostic/manifest.json')
assert freeze['source_hashes']==m['source_hashes'] and freeze['binary_sha256']==m['binary_sha256']
for p,h in freeze['source_hashes'].items():assert sha(source/p)==h,p
assert sha(source/'study-configs/readiness-diagnostic.json')==freeze['specs']['diagnostic']
assert study.audit(data/'diagnostic')['passed']
results={}
for name in study.VARIANTS:
 case=data/'diagnostic/moving_shared-3241'/name
 a=analyze_case(case);events=load(case/'request-trace.json')['events'];requests=load(case/'requests.json');r=load(case/'result.json')
 opens=sorted([e for e in events if e['op']=='open'],key=lambda e:e['start_ns']);copies=[e for e in events if e['op']=='copy_pipeline']
 active=[];overlap=[]
 for request,o in zip(requests,opens):
  if o['tier']!='remote':continue
  same=[e for e in copies if e['path']==o['path'] and e['start_ns']<request['read_done_ns'] and e['end_ns']>o['start_ns']]
  if same:overlap.append(request['index'])
  for e in same:
   if e['start_ns']<=o['end_ns']<e['end_ns']:
    active.append(dict(index=request['index'],remaining_copy_ms=(e['end_ns']-o['end_ns'])/1e6,remote_read_ms=(request['read_done_ns']-request['opened_ns'])/1e6));break
 results[name]=dict(audit_passed=a['passed'],event_count=a['event_count'],requests=a['requests'],diagnostic_mib_s=r['effective_mib_s'],
  commit_copy_cost_rejections=r['metrics'].get('measured_commit_copy_cost',0),remote_opens=r['metrics']['remote_read_open_count'],
  same_object_copy_overlap=len(overlap),same_object_copy_active_at_open=len(active),active=active,
  active_remaining_ms=statistics.mean(x['remaining_copy_ms'] for x in active) if active else None)
# Keep the original driver failure and original log untouched.
result=dict(passed=True,original_driver_exit=int((data/'diagnostic.exit').read_text()),original_driver_report_failed=True,
 source_files_verified=len(freeze['source_hashes']),requests=1152,results=results,
 limits='Two instrumented diagnostic replays, not confirmation; original report-generation WAL snapshot failure preserved. Prior seed3241 cost rejections not reproduced. Overlap is not a causal speedup.')
(root/'readiness-diagnostic-review.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
