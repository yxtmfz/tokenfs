from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parent
src=Path('/Users/mafuze/Documents/Codex/2026-09-18/new-chat/work/tokenfs-eval/src')
expected=json.loads((root/'results.json').read_text())
admissions=json.loads((root/'admissions.json').read_text())
tested=0;compared_admissions=0
for h in ['retained','opportunity74']:
 d=root/'source-replay'/h;d.mkdir(parents=True,exist_ok=True)
 for f in ['measured_policy.h','run_reuse.h']:(d/f).write_bytes((src/f).read_bytes())
 replay=(root/(h+'_object_prior')/'replay.cpp').read_text()
 replay=replay.replace('o.recent_value_floor=true;','o.object_weighted_cohort_prior=true;o.recent_value_floor=true;')
 (d/'replay.cpp').write_text(replay)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
 for row in expected['rows']:
  raw=subprocess.run([str(d/'replay'),str(root/'inputs'/(row['input']+'.txt')),'prior'],capture_output=True,text=True,check=True)
  assert raw.stdout==row['variants'][h+'_object_prior']['stdout'],(h,row['input'])
  source_rows=[]
  for line in raw.stderr.splitlines():
   a,t,k,location,reason,cohort,incoming,loss,copy,noise,victims=line.split('\t')
   source_rows.append({'input':row['input'],'variant':h+'_object_prior','arm':a,'observation':int(t),'key':k,'location':int(location),'reason':reason,'cohort_disk_reuse':float(cohort),'incoming_us':float(incoming),'displaced_us':float(loss),'copy_us':float(copy),'uncertainty_us':float(noise),'victim_count':int(victims)})
  target=[r for r in admissions if r['input']==row['input'] and r['variant']==h+'_object_prior']
  assert source_rows==target,(h,row['input'],'admission mismatch')
  compared_admissions+=len(target);tested+=4
result={'passed':True,'source_arms':tested,'exact_admission_records':compared_admissions,'optimized_counter_equals_scanning_model':True,'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [src/'run_reuse.h',src/'measured_policy.h']}}
(root/'source-equivalence.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ['replay','prior_test','manifest.json']}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
