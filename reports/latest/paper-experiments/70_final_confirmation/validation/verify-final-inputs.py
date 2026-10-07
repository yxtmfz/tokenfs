from pathlib import Path
import gzip,json,hashlib,tarfile,sys
root=Path(sys.argv[1]).resolve();sha=lambda b:hashlib.sha256(b).hexdigest()
f=json.loads((root/'provenance/final-hpj-public.json').read_text())
rawbytes=gzip.decompress((root/'provenance/toolagent-source.jsonl.gz').read_bytes());assert sha(rawbytes)==f['source_sha256']
raw=[json.loads(x) for x in rawbytes.decode().splitlines()];used=set()
with tarfile.open(root/'provenance/prior-public-traces.tar.gz') as t:
 for old in f['prior_trace_files']:
  b=t.extractfile(old['sha256']+'.json').read();assert sha(b)==old['sha256'];rows=json.loads(b)
  ids={e['source_request'] for e in rows if 'source_request' in e}
  assert min(ids)==old['first'] and max(ids)==old['last'];used.update(ids)
for x in f['windows']:
 assert not set(range(x['start'],x['end']+1))&used
 ev=[];keys={}
 for j in range(x['start'],x['end']+1):
  for h in raw[j]['hash_ids']:
   ev.append(dict(index=len(ev),key=keys.setdefault(str(h),len(keys)),caller=j%3,bytes=2097152,source_request=j,source_hash=str(h),source_arrival_ms=raw[j]['timestamp']-raw[x['start']]['timestamp']))
   if len(ev)==1152:break
  if len(ev)==1152:break
 assert ev==x['events'] and j==x['end']
print(json.dumps(dict(passed=True,source_sha256=f['source_sha256'],historical_traces_verified=len(f['prior_trace_files']),public_rows=[[x['start'],x['end']] for x in f['windows']],timing_used_for_selection=False)))
