from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parent
baseline=json.loads((root.parents[1]/'hotspot-object77/capacity-boundary/results.json').read_text())
rows=[]
(root/"logs").mkdir(exist_ok=True)
for p in sorted((root/'inputs').glob('*.txt')):
 old=next(r for r in baseline['rows'] if r['input']==p.stem and r['capacity_mib_global']==24)['variants']['object_weighted']
 r={'input':p.stem,'variants':{}}
 for mode in ['lru','ranked','marginal']:
  raw=subprocess.run([str(root/'replay'),str(p),mode,str(root/"logs"/(p.stem+"-"+mode+".tsv"))],check=True,capture_output=True,text=True)
  (root/(p.stem+'-'+mode+'.txt')).write_text(raw.stdout)
  arms={line.split()[0]:{k:int(v) for k,v in (x.split('=') for x in line.split()[1:])} for line in raw.stdout.splitlines()}
  for arm,a in arms.items():
   assert a['remote']+a['disk_hits']+a['ram_hits']==a['requests']==1152
   a['fixed_storage_cost_ms']=a['remote']*21+a['disk_hits']*10.5+a['copies']*8
   if mode=='lru':
    for k in ['remote','copies','ram_hits','disk_hits','requests']:assert a[k]==old[arm][k],(p,arm,k)
  r['variants'][mode]=arms
 rows.append(r)
d={'speed_evidence':False,'description':'Original frozen78 policy headers (same H as77), all10 existing inputs x three RAM policies x four arms=120 local arms. Disk=3 domains x4 objects=24MiB. RAM exactly2 slots/4MiB, always retains current read capture, evicts one unpinned old capture. Ranked candidate uses original H Ranked and original static-value Ranked for NoH; NoP/NoJ retain own Options. Ranked uses coverage=1 for all candidates; marginal uses coverage=1 when a readable disk copy exists, otherwise2 derived from fixed21/10.5ms service costs, identically for H and NoH. No arbitrary ratio scan. Fixed 21ms remote/10.5ms disk/8ms copy, RAM0, instant copies/serial requests. No real speed/p99 inference. PoolSIEVE implementation remains unchanged LRU and is not among this four-arm policy replay.','rows':rows}
(root/'results.json').write_text(json.dumps(d,indent=2)+'\n')
lines=['|Input|RAM|Full R/D/RAM/copy|NoH R/D/RAM/copy|Full saving vs NoH ms|Full saving vs LRU Full ms|','|---|---|---:|---:|---:|---:|']
for r in rows:
 for mode,a in r['variants'].items():
  f=a['Full'];h=a['NoHotspot'];orig=r['variants']['lru']['Full'];fmt=lambda x:'/'.join(str(x[k]) for k in ['remote','disk_hits','ram_hits','copies'])
  lines.append(f"|{r['input']}|{mode}|{fmt(f)}|{fmt(h)}|{h['fixed_storage_cost_ms']-f['fixed_storage_cost_ms']}|{orig['fixed_storage_cost_ms']-f['fixed_storage_cost_ms']}|")
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
(root/'verification.json').write_text(json.dumps({'passed':True,'arms':120,'baseline40_reproduced':True,'request_accounting':True,'always_admit_current_and_max2_slots_runtime_guard':True,'headers':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.glob('*.h')}},indent=2)+'\n')
