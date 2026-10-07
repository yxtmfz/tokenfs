from pathlib import Path
import json,hashlib,collections,statistics
out=Path(__file__).resolve().parent
work=out.parent;repo=work/'tokenfs-eval';base=work/'hotspot-object77/tail-evidence'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs={};arms={}
for arm in ('Full','NoHotspot'):
 case=base/arm;t=json.loads((case/'request-trace.json').read_text());r=json.loads((case/'result.json').read_text())
 assert t['dropped']==0
 for name in ['request-trace.json','result.json']:inputs[str((case/name).relative_to(work))]=sha(case/name)
 byhandle=collections.defaultdict(list);groups=collections.defaultdict(list)
 for e in t['events']:
  if e['op']!='read':continue
  byhandle[e['handle']].append(e)
  kind='EOF' if not e['bytes'] else 'data-pread' if e['pread_ns'] else 'captured-tail'
  groups[(e['tier'],kind)].append(e)
 sequences=collections.Counter(tuple((e['bytes'],bool(e['pread_ns'])) for e in sorted(es,key=lambda e:e['start_ns'])) for es in byhandle.values())
 summaries=[]
 for (tier,kind),events in sorted(groups.items()):
  p=[e['pread_ns'] for e in events];c=[e['end_ns']-e['start_ns'] for e in events]
  summaries.append(dict(tier=tier,kind=kind,n=len(events),returned_bytes=sum(e['bytes'] for e in events),pread_mean_us=statistics.mean(p)/1000,pread_sum_ms=sum(p)/1e6,callback_mean_us=statistics.mean(c)/1000,callback_sum_ms=sum(c)/1e6))
 pread=[e for es in byhandle.values() for e in es if e['pread_ns']]
 assert len(pread)==r['metrics']['direct_backend_pread_ops']==3450
 assert sum(e['bytes'] for es in byhandle.values() for e in es)==r['metrics']['read_bytes']
 # Every non-RAM handle has exactly two data-bearing syscalls and one EOF syscall.
 for es in byhandle.values():
  if es[0]['tier']=='inflight':assert not any(e['pread_ns'] for e in es);continue
  assert sum(e['bytes']>0 and e['pread_ns']>0 for e in es)==2
  assert sum(e['bytes']==0 and e['pread_ns']>0 for e in es)==1
 arms[arm]=dict(handles=len(byhandle),groups=summaries,
   sequences=[dict(count=n,callback_bytes_and_pread=list(seq)) for seq,n in sequences.items()],
   aggregate_metrics={k:v for k,v in r['metrics'].items() if k.startswith('direct_backend') or k in ['direct_read_tail_hits','direct_read_tail_bytes']})
refs=['tokenfs-eval/src/main.cpp','tokenfs-eval/src/aligned_read.h','tokenfs-eval/src/read_fill.h','tokenfs-eval/scripts/evidence_benchmark.py','cn7-debs/libfuse3-dev_3.14.0-5build1_amd64.deb','affinity-shared-preflight-cn7.json','hotspot-indexed80/build.log','hotspot-fuse-read-review/fuse3-package/usr/include/fuse3/fuse_common.h']
for name in refs:inputs[name]=sha(work/name)
(out/'evidence.json').write_text(json.dumps(dict(scope='Frozen77 diagnostic trace and local headers; no server execution; not candidate80 speed evidence',inputs_sha256=inputs,arms=arms),indent=2)+'\n')
print('PASS: both arms, 1152 handles each, 2 data preads + 1 EOF per disk handle; 3450 preads per arm')
