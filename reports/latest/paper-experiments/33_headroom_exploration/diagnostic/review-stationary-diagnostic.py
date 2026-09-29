from pathlib import Path
import json,sys,hashlib,statistics
root=Path(__file__).resolve().parent;data=root/'stationary-diagnostic-data';source=root/'burst-interval-source'
sys.path.insert(0,str(source/'scripts'))
import burst_interval_study as s
from tail_diagnostic_analysis import analyze_case
load=lambda p:json.loads(p.read_text());m=load(data/'manifest.json');freeze=m['freeze']
for p,h in freeze['source_hashes'].items():assert hashlib.sha256((source/p).read_bytes()).hexdigest()==h
assert m['binary_sha256']==freeze['binary_sha256'] and m['diagnostic_only']
assert m['trace']==s.trace(m['spec']) and m['spec']==s.expected_spec()['blocks'][0]
results=[]
for arm in m['order']:
 case=data/arm;r=load(case/'result.json');cfg=load(case/'config.json');a=analyze_case(case)
 assert a==load(case/'diagnosis.json')
 expected=s.configuration(arm,Path('/home/wjxt/tokenfs-stationary-diagnostic-20260929')/arm,Path('/srv/tokenfs/remote-cn7/stationary-diagnostic-20260929'),24,True)
 expected['policy'].update(request_trace_path=str(Path('/home/wjxt/tokenfs-stationary-diagnostic-20260929')/arm/'request-trace.json'),profile_control_path=True)
 assert cfg==expected
 assert all(n<=g['local_quota_mib']*s.MIB for n,g in zip(r['retained_cache_bytes'],cfg['gpus']))
 metrics=r['metrics'];rows=a['request_details'];trace=load(case/'request-trace.json')
 assert len(rows)==576 and metrics['read_bytes']==576*2*s.MIB
 assert metrics['background_submitted']==metrics['background_completed']
 assert metrics['read_fill_buffer_peak_bytes']<=4*s.MIB
 assert not any(v for k,v in metrics.items() if k.endswith('error_count'))
 tiers=[]
 for tier in ['local','remote','inflight']:
  rr=[x for x in rows if x['tier']==tier]
  assert len(rr)==metrics.get(tier+'_read_open_count',0)
  assert sum(e['bytes'] for e in trace['events'] if e['op']=='read' and e['tier']==tier)==metrics.get('read_'+tier+'_bytes',0)
  tiers.append(dict(tier=tier,opens=len(rr),mib=metrics.get('read_'+tier+'_bytes',0)/s.MIB,mean_response_ms=statistics.mean(x['response_ms'] for x in rr) if rr else None))
 assert sum(x['opens'] for x in tiers)==576
 results.append(dict(strategy=arm,diagnostic_only=True,means=a['all_means'],tiers=tiers,copy_count=a['copy_count'],diagnostic_mib_s=a['diagnostic_mib_s']))
answer=dict(passed=True,runs=2,requests=1152,results=results,note='Original analyzer strata omitted inflight, but all_means included it. This review explicitly validates and includes all three tiers; no original data overwritten.')
(root/'stationary-diagnostic-review.json').write_text(json.dumps(answer,indent=2)+'\n')
print(json.dumps(answer,indent=2))
