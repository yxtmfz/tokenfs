from pathlib import Path
import json,random,sys,hashlib
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';sys.path.insert(0,str(r/'scripts'))
from affinity_v3_study import SCENES,VARIANTS
from measured_study import application,digest
src=w/'public-traces/toolagent_trace.jsonl';raw=[json.loads(x) for x in src.read_text().splitlines()];cut=len(raw)//5
old=json.loads((r/'study-configs/measured-b3-freeze.json').read_text())
used=[(x['first_source_request'],x['last_source_request']) for x in old['public_windows'] if x['source']=='toolagent_trace.jsonl']
old3=json.loads((r/'study-configs/affinity-joint-public-windows.json').read_text())
used += [(x['first'],x['last']) for x in old3['windows']]
old4=json.loads((r/'study-configs/affinity-v2-public-windows.json').read_text())
used += [(x['first'],x['last']) for x in old4['windows']]
windows=[]
def public(seed,stage,index,count,shard):
    if stage!='confirmation':offset=100+index*300;split='development'
    else:
        split='confirmation';start=cut+index*(len(raw)-cut)//12+400
        while True:
            offset=start-cut
            _,events,origin=application(src,split,offset,count,shard)
            assert len(events)==count,'source window exhausted'
            end=max(e['source_request'] for e in events)
            overlap=[b for a,b in used if not (end<a or start>b)]
            if not overlap:break
            start=max(overlap)+20
        used.append((start,end))
    _,events,origin=application(src,split,offset,count,shard)
    for e in events:e['caller']=e['source_request']%3
    if stage=='confirmation':windows.append(dict(seed=seed,first=min(e['source_request'] for e in events),last=max(e['source_request'] for e in events),trace_sha256=digest(events),source_sha256=origin['sha256']))
    return events,origin
for stage,seeds in [('correctness',[1691]),('development',[1701,1702]),('confirmation',list(range(1901,1913)))]:
    blocks=[]
    for index,seed in enumerate(seeds):
        for scene in SCENES:
            n=96 if stage=='correctness' else 384;shard=1 if stage=='correctness' else 2
            if scene=='affinity_handover' and stage=='correctness':n=384
            if scene=='public_toolagent':n=96 if stage=='correctness' else 768;shard=1
            b=dict(id=f'{scene}-s{seed}',scenario=scene,seed=seed,requests=n,shard_mib=shard,quota_mib=4 if stage=='correctness' else 8,variants=VARIANTS)
            if scene=='public_toolagent':b['events'],b['public_origin']=public(seed,stage,index,n,shard)
            blocks.append(b)
    random.Random(9501).shuffle(blocks)
    (r/f'study-configs/affinity-v3-{stage}-01.json').write_text(json.dumps(dict(stage=stage,topology='three private logical domains on one client disk; actual NVMe/TCP',blocks=blocks),indent=2)+'\n')
(r/'study-configs/affinity-v3-public-windows.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(src.read_bytes()).hexdigest(),source_commit='97030cacfbf8db7d0098e35da46c58abbae04593',windows=windows,disjoint_from=['measured-b3-freeze.json','affinity-joint-public-windows.json','affinity-v2-public-windows.json']),indent=2)+'\n')
print('24 correctness/host;48 development;288 fresh confirmation;12 public windows disjoint from all prior confirmation')
