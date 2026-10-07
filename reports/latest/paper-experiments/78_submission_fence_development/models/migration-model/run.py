from pathlib import Path
import subprocess,json,csv,hashlib
root=Path(__file__).resolve().parent
baseline=json.loads((root.parents[1]/'hotspot-object77/capacity-boundary/results.json').read_text())
rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 old=next(r for r in baseline['rows'] if r['input']==p.stem and r['capacity_mib_global']==24)['variants']['object_weighted']
 r={'input':p.stem,'modes':{}}
 for mode in ['baseline','original_ram','spill','conditional_ram','common_ram','bootstrap','common_ram_bootstrap','censored','common_ram_censored']:
  folder=root/mode;folder.mkdir(exist_ok=True)
  raw=subprocess.run([str(root/'replay'),str(p),mode,str(folder/(p.stem+'.tsv'))],check=True,text=True,capture_output=True)
  (folder/(p.stem+'.txt')).write_text(raw.stdout)
  arms={line.split()[0]:{k:int(v) for k,v in (x.split('=') for x in line.split()[1:])} for line in raw.stdout.splitlines()}
  for arm,a in arms.items():
   a['fixed_storage_cost_ms']=a['remote']*21+a['disk_hits']*10.5+a['copies']*8
   assert a['remote']+a['disk_hits']+a['ram_hits']==a['requests']==1152
   if mode=='baseline' or (arm=='NoHotspot' and mode not in ['common_ram','bootstrap','common_ram_bootstrap','common_ram_censored']):
    for k in ['remote','copies','ram_hits','disk_hits','requests']:assert a[k]==old[arm][k],(mode,p,arm,k,a[k],old[arm][k])
  r['modes'][mode]=arms
 rows.append(r)
result={'speed_evidence':False,'description':'Frozen77 policy migration mechanism models, 10 existing fixed inputs x 9 modes x 4 arms =360. First-run cohort stratification uses past completed first-run lengths and already-observed recurrence only; RAM-admit uses current observed prefix. Spill postpones admission until actual 2-object RAM eviction. NoHotspot unchanged in H-only candidates; common modes apply the same executor change to all arms. H-only RAM trigger controls cannot establish H-specific contribution. Fixed additive cost is not walltime/p99. All arms, inputs and traces retained.','rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['|Input|Mode|Full remote/copy|NoH remote/copy|Full saving vs NoH ms|Full saving vs old Full ms|','|---|---|---:|---:|---:|---:|']
for r in rows:
 for mode,a in r['modes'].items():
  f=a['Full'];n=a['NoHotspot'];old=r['modes']['baseline']['Full']
  lines.append(f"|{r['input']}|{mode}|{f['remote']}/{f['copies']}|{n['remote']}/{n['copies']}|{n['fixed_storage_cost_ms']-f['fixed_storage_cost_ms']}|{old['fixed_storage_cost_ms']-f['fixed_storage_cost_ms']}|")
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
(root/'verification.json').write_text(json.dumps({'passed':True,'baseline_arms_reproduced':40,'noH_unchanged_cases':50,'arms':360},indent=2)+'\n')
