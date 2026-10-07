from pathlib import Path
import hashlib,json
w=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-caller-independent';src=w/(tag+'-source')
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frozen=load(src/'study-configs/independent-hpj-public.json')
source=w/'public-traces/toolagent_trace.jsonl';assert sha(source)==frozen['source_sha256']
raw=[json.loads(x) for x in source.read_text().splitlines()]
used=set()
for old in frozen['prior_trace_files']:
 p=w/old['path'];assert sha(p)==old['sha256']
 rows=load(p);ids={e['source_request'] for e in rows if 'source_request' in e}
 assert min(ids)==old['min'] and max(ids)==old['max'];used.update(ids)
for p in (src/'study-configs').glob('*public-windows.json'):
 for win in load(p).get('windows',[]):used.update(range(win['first'],win['last']+1))
reviews=[]
for win in frozen['windows']:
 ids=set(range(win['start'],win['end']+1));assert not ids&used;used.update(ids)
 events=[];keys={}
 for j in range(win['start'],win['end']+1):
  for h in raw[j]['hash_ids']:
   events.append(dict(index=len(events),key=keys.setdefault(str(h),len(keys)),caller=j%3,bytes=2*1048576,source_request=j,source_hash=str(h),source_arrival_ms=raw[j]['timestamp']-raw[win['start']]['timestamp']))
   if len(events)==1152:break
  if len(events)==1152:break
 assert events==win['events'] and j==win['end']
 reviews.append(dict(first=win['start'],last=win['end'],requests=len(events),unique_objects=len(keys),passed=True))
out=dict(passed=True,source_sha256=frozen['source_sha256'],prior_trace_files_verified=len(frozen['prior_trace_files']),windows=reviews,scope='source request rows disjoint from enumerated local historical traces and frozen public-window manifests; repeated objects across windows remain possible')
(w/'independent-input-review.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
