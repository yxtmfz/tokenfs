from pathlib import Path
import subprocess,json,hashlib,tarfile,shutil,collections
root=Path(__file__).resolve().parent
repo=Path('/Users/mafuze/Documents/Codex/2026-09-18/new-chat/work/tokenfs-eval')
baseline=repo/'reports/latest/paper-experiments/75_read_path_diagnostic/models/capacity-model'
source_tar=root.parent/'source.tar.gz'
root.joinpath('native').mkdir(exist_ok=True)
with tarfile.open(source_tar) as tf:
 for name in ['run_reuse.h','measured_policy.h']:
  matching=[m for m in tf.getmembers() if m.isfile() and m.name.endswith('/src/'+name)]
  if not matching:matching=[m for m in tf.getmembers() if m.isfile() and m.name=='src/'+name]
  assert len(matching)==1,(name,[m.name for m in matching])
  root.joinpath('native',name).write_bytes(tf.extractfile(matching[0]).read())
shutil.copytree(baseline.parent/'disk-model/inputs',root/'inputs',dirs_exist_ok=True)
replay=(baseline/'retained/replay.cpp').read_text()
replay=replay.replace('o.disk_opportunity_value=false;','o.object_weighted_cohort_prior=true;o.disk_opportunity_value=false;')
replay=replay.replace('i=0,remote=0,copies=0;', 'i=0,remote=0,copies=0,ram_hits=0,disk_hits=0;')
replay=replay.replace('   if(captured||local)continue;++remote;', '   if(captured)++ram_hits;else if(local)++disk_hits;\n   if(captured||local)continue;++remote;')
replay=replay.replace('<<" copies="<<copies;', '<<" copies="<<copies<<" ram_hits="<<ram_hits<<" disk_hits="<<disk_hits<<" requests="<<i;')
(root/'native/replay.cpp').write_text(replay)
subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(root/'native'),str(root/'native/replay.cpp'),'-o',str(root/'native/replay')],check=True)
prior=json.loads((baseline/'results.json').read_text());rows=[];equality_checks=0
def storage_score(a):return a['remote']*21.0+a['disk_hits']*10.5+a['copies']*8.0
for p in sorted((root/'inputs').glob('*.txt')):
 events=[line.split()[0] for line in p.read_text().splitlines()];ram=[];ramhits=0
 for key in events:
  if key in ram:ramhits+=1;ram.remove(key)
  ram.append(key)
  if len(ram)>2:ram.pop(0)
 for capacity in [2,3,4,8]:
  prev=next(r for r in prior['rows'] if r['input']==p.stem and r['capacity_objects_per_domain']==capacity)
  old=json.loads(json.dumps(prev['variants']['retained']['arms']))
  raw=subprocess.run([str(root/'native/replay'),str(p),'prior',str(capacity)],capture_output=True,text=True,check=True)
  candidate={}
  for line in raw.stdout.splitlines():
   cells=line.split();candidate[cells[0]]={k:int(v) for k,v in (cell.split('=') for cell in cells[1:])}
  assert {k:candidate['NoHotspot'][k] for k in old['NoHotspot']}==old['NoHotspot'],(p,capacity,'NoH changed')
  equality_checks+=1
  for a in candidate.values():assert a['remote']+a['disk_hits']+a['ram_hits']==a['requests']==len(events) and a['ram_hits']==ramhits
  for a in old.values():a.update(ram_hits=ramhits,disk_hits=len(events)-ramhits-a['remote'],requests=len(events))
  for variants in [candidate,old]:
   for a in variants.values():a['fixed_storage_cost_ms']=storage_score(a)
  compare={}
  for name,arms in [('object_weighted',candidate),('legacy_event_prior',old)]:
   compare[name]={other:{'remote_reduction':arms[other]['remote']-arms['Full']['remote'],'extra_copies':arms['Full']['copies']-arms[other]['copies'],'fixed_cost_saving_ms':arms[other]['fixed_storage_cost_ms']-arms['Full']['fixed_storage_cost_ms']} for other in ['NoHotspot','NoAffinity','NoJoint']}
  rows.append({'input':p.stem,'capacity_mib_global':capacity*6,'capacity_objects_per_domain':capacity,'new_stdout':raw.stdout,'variants':{'object_weighted':candidate,'legacy_event_prior':old},'full_comparisons':compare,'new_vs_old_full_fixed_cost_saving_ms':old['Full']['fixed_storage_cost_ms']-candidate['Full']['fixed_storage_cost_ms']})
result={'speed_evidence':False,'description':'Frozen77 actual H headers, 4 capacities(12/18/24/48 MiB) × 10 known inputs × 4 arms =160 new model arms. Original retained-capacity model reused as explicit old-data mechanism reference; it is not fresh server data. Fixed storage-cost score=remote_reads*21ms + disk_hits*10.5ms + copies*8ms, with RAM service cost zero. This additive score ignores asynchronous overlap, control costs and real contention, so it is neither wall time nor throughput nor p99. Original24MiB primary acceptance unchanged; other capacities are boundary diagnostics only.','source_tar_sha256':hashlib.sha256(source_tar.read_bytes()).hexdigest(),'headers':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'native').glob('*.h')},'baseline_results_sha256':hashlib.sha256((baseline/'results.json').read_bytes()).hexdigest(),'rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Capacity boundary diagnostic for frozen77 H','',result['description'],'','Every cell: remote reads / copies / fixed storage cost ms.','', '|Input|Global MiB|H|Full|NoH|NoP|NoJ|Full saving vs NoH ms|','|---|---:|---|---:|---:|---:|---:|---:|']
for r in rows:
 for name,a in r['variants'].items():
  cells=[' / '.join(str(a[k][x]) for x in ['remote','copies','fixed_storage_cost_ms']) for k in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+r['input']+' | '+str(r['capacity_mib_global'])+' | '+name+' | '+' | '.join(cells)+' | '+str(r['full_comparisons'][name]['NoHotspot']['fixed_cost_saving_ms'])+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n')
summary=[]
for capacity in [12,18,24,48]:
 for family in ['moving_shared','public_toolagent','stationary_shared','uniform']:
  relevant=[r for r in rows if r['capacity_mib_global']==capacity and r['input'].startswith(family+'-')]
  values=[r['full_comparisons']['object_weighted']['NoHotspot']['fixed_cost_saving_ms'] for r in relevant]
  summary.append({'capacity_mib_global':capacity,'family':family,'inputs':len(values),'better_than_noH':sum(v>0 for v in values),'equal_to_noH':sum(v==0 for v in values),'worse_than_noH':sum(v<0 for v in values),'saving_range_ms':[min(values),max(values)]})
(root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
(root/'verification.json').write_text(json.dumps({'passed':True,'new_arms':160,'NoH_equal_old_model_cases':equality_checks,'request_accounting_all_arms':True,'frozen77_headers':result['headers']},indent=2)+'\n')
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ['replay','manifest.json']}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(summary,indent=2))
for r in rows:
 if r['input'] in ['moving_shared-74801','public_toolagent-74802']:
  print(r['input'],r['capacity_mib_global'],r['full_comparisons']['object_weighted']['NoHotspot'],r['variants']['object_weighted']['Full']['remote'],r['variants']['object_weighted']['Full']['copies'])
