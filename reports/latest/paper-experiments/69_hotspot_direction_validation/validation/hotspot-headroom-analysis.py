from pathlib import Path
import json,math,collections,re
root=Path(__file__).resolve().parent;data=root/'integrated-hpj-cohort-caller-independent-data/development';out=[]
for f in sorted(data.glob('*/trace.json')):
 t=json.loads(f.read_text());seen=set();first=set();run_counts=collections.Counter()
 for i,e in enumerate(t):
  if e['key'] not in seen:first.add(i);seen.add(e['key'])
  if not i or t[i-1]['key']!=e['key']:run_counts[e['key']]+=1
 arms=[]
 for arm in ['Full','NoHotspot']:
  p=f.parent/arm
  if not p.exists():continue
  r=json.loads((p/'result.json').read_text());rows=json.loads((p/'requests.json').read_text());events=json.loads((p/'policy-events.json').read_text())
  slow=sorted(rows,key=lambda x:x['response_seconds'],reverse=True)[:math.ceil(.01*len(rows))]
  ads=[e for e in events if e['action']=='ADMIT'];keys=[int(re.search(r'shard-(\d+)',e['logical_path'])[1]) for e in ads]
  arms.append(dict(variant=arm,remote_reads=r['metrics']['remote_read_open_count'],copy_admissions=len(ads),copy_admissions_of_single_run_keys=sum(run_counts[k]==1 for k in keys),top_one_percent_requests=len(slow),top_one_percent_first_references=sum(x['index'] in first for x in slow)))
 out.append(dict(input=f.parent.name,requests=len(t),distinct_keys=len(seen),logical_disk_object_capacity=12,logical_capture_object_capacity=2,arms=arms))
ans=dict(source_report=66,analysis_type='offline diagnostic using complete inputs; not online policy inputs',scenes=out,limits='First-reference classification is observable from the prefix, but single-run classification uses the full trace only for diagnosis. Counts are logical requests, not packet or device metrics.')
(root/'hotspot-headroom-analysis.json').write_text(json.dumps(ans,indent=2)+'\n');print(json.dumps(ans,indent=2))
