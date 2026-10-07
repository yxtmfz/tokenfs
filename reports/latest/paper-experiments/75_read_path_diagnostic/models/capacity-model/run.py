from pathlib import Path
import shutil,subprocess,json,hashlib
root=Path(__file__).resolve().parent
src=root.parent/'disk-model'
shutil.copytree(src/'inputs',root/'inputs',dirs_exist_ok=True)
variants=['retained','opportunity74']
for variant in variants:
 d=root/variant;d.mkdir(exist_ok=True)
 for name in ['measured_policy.h','run_reuse.h']:(d/name).write_bytes((src/variant/name).read_bytes())
 replay=(src/variant/'replay.cpp').read_text()
 replay=replay.replace(' for(std::string arm:', ' const int capacity=argc>3?std::stoi(argv[3]):4;\n if(capacity<1)return 2;\n for(std::string arm:')
 assert '4*size,o)' in replay
 replay=replay.replace('4*size,o)','capacity*size,o)')
 (d/'replay.cpp').write_text(replay)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 for capacity in [2,3,4,8]:
  row={'input':p.stem,'capacity_objects_per_domain':capacity,'capacity_mib_global':capacity*3*2,'variants':{}}
  for variant in variants:
   result=subprocess.run([str(root/variant/'replay'),str(p),'prior',str(capacity)],capture_output=True,text=True,check=True)
   arms={}
   for line in result.stdout.splitlines():
    cells=line.split();arms[cells[0]]={k:int(v) for k,v in [cell.split('=') for cell in cells[1:]]}
   row['variants'][variant]={'stdout':result.stdout,'arms':arms}
  assert row['variants']['retained']['arms']['NoHotspot']==row['variants']['opportunity74']['arms']['NoHotspot']
  rows.append(row)
result={'speed_evidence':False,'description':'Fixed capacities 2/3/4/8 objects per domain, 3 domains, 2 MiB objects; 10 inspected inputs × 2 frozen H algorithms × 4 capacities × 4 arms = 320 model arms. Constant 21 ms remote read, 10.5 ms local, 8 ms copy, instantaneous copy. No throughput/p99 evidence and no claim original 24 MiB condition passes.','rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Fixed capacity sensitivity model','',result['description'],'','| Input | Global MiB | H variant | Full remote/copies | NoH remote/copies | NoP remote/copies | NoJ remote/copies |','|---|---:|---|---:|---:|---:|---:|']
for row in rows:
 for variant in variants:
  a=row['variants'][variant]['arms'];cells=[f"{a[k]['remote']}/{a[k]['copies']}" for k in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+row['input']+' | '+str(row['capacity_mib_global'])+' | '+variant+' | '+' | '.join(cells)+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='manifest.json'}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
