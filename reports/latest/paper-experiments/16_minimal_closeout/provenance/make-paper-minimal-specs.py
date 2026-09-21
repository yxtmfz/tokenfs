from pathlib import Path
import json,random,sys,hashlib
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';sys.path.insert(0,str(r/'scripts'))
from paper_minimal_study import MAIN,VARIANTS,SCENES
from measured_study import application,digest
src=w/'public-traces/toolagent_trace.jsonl';raw=[json.loads(x) for x in src.read_text().splitlines()];cut=len(raw)//5
old=json.loads((r/'study-configs/measured-b3-freeze.json').read_text())
used=[(x['first_source_request'],x['last_source_request']) for x in old['public_windows'] if x['source']=='toolagent_trace.jsonl']
for f in ['affinity-joint','affinity-v2','affinity-v3']:
 used += [(x['first'],x['last']) for x in json.loads((r/f'study-configs/{f}-public-windows.json').read_text())['windows']]
windows=[]
def public(seed,stage,index,count,shard):
 if stage!='confirmation':offset=100+index*300;split='development'
 else:
  split='confirmation';start=cut+index*(len(raw)-cut)//12+800
  while True:
   offset=start-cut;_,events,origin=application(src,split,offset,count,shard)
   end=max(e['source_request'] for e in events)
   overlap=[b for a,b in used if not (end<a or start>b)]
   if not overlap:break
   start=max(overlap)+20
  used.append((start,end))
 _,events,origin=application(src,split,offset,count,shard)
 for e in events:e['caller']=e['source_request']%3
 if stage=='confirmation':windows.append(dict(seed=seed,first=min(e['source_request'] for e in events),last=max(e['source_request'] for e in events),trace_sha256=digest(events),source_sha256=origin['sha256']))
 return events,origin
for stage,seeds in [('correctness',[2001]),('development',[2011]),('confirmation',list(range(2101,2113)))]:
 blocks=[]
 for index,seed in enumerate(seeds):
  for scene in SCENES:
   n=192 if stage=='correctness' else 384;shard=1 if stage=='correctness' else 2
   if scene=='public_toolagent':n=192 if stage=='correctness' else 768;shard=1
   variants=MAIN.copy()
   if scene=='hot_shift':variants+=['no-H','no-J','no-HJ']
   if scene=='public_toolagent':variants+=['no-J']
   b=dict(id=f'{scene}-s{seed}',scenario=scene,seed=seed,requests=n,shard_mib=shard,quota_mib=4 if stage=='correctness' else 8,variants=variants)
   if scene=='public_toolagent':b['events'],b['public_origin']=public(seed,stage,index,n,shard)
   blocks.append(b)
 random.Random(10051).shuffle(blocks)
 (r/f'study-configs/paper-minimal-{stage}-01.json').write_text(json.dumps(dict(stage=stage,topology='three private logical domains; storage replay, no physical GPU claim',blocks=blocks),indent=2)+'\n')
 print(stage,sum(len(b['variants']) for b in blocks))
blocks=[]
for seed in [2201,2202,2203]:
 for condition,n,quota in [('hot_shift_q16',384,16),('hot_shift_long',1536,8)]:
  blocks.append(dict(id=f'{condition}-s{seed}',condition=condition,scenario='hot_shift',seed=seed,requests=n,shard_mib=2,quota_mib=quota,variants=['Full','RecentLFU']))
random.Random(10052).shuffle(blocks)
(r/'study-configs/paper-minimal-sensitivity-01.json').write_text(json.dumps(dict(stage='development',purpose='fixed descriptive sensitivity only; no policy tuning or confirmed claims',blocks=blocks),indent=2)+'\n')
(r/'study-configs/paper-minimal-public-windows.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),windows=windows,disjoint_from=['measured-b3-freeze','affinity-joint','affinity-v2','affinity-v3']),indent=2)+'\n')
