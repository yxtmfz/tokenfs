from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parent
outputs=[]
for variant,arg in [('cohort_beta_outcome','beta'),('cohort_hit_outcome','hits')]:
 exe=root/variant/'verify'
 subprocess.run(['c++','-std=c++17','-O2','-I',str(root/variant),str(root/'verify.cpp'),'-o',str(exe)],check=True)
 p=subprocess.run([str(exe),arg],check=True,capture_output=True,text=True);outputs.append(dict(variant=variant,stdout=p.stdout))
result=json.loads((root/'results.json').read_text());old=json.loads((root.parent/'disk-model/results.json').read_text())
for row in result['rows']:
 original=next(r for r in old['rows'] if r['input']==row['input'])
 assert row['variants']['retained']['arms']==original['variants']['retained']['arms']
 for variant in ['cohort_beta_outcome','cohort_hit_outcome']:
  for arm in row['variants'][variant]['arms'].values():
   assert arm['newcopies']==arm['closed_new']+arm['censored_new']
   assert arm['closed_success']<=arm['closed_new'] and arm['closed_success']<=arm['closed_hits']
   assert arm['calibration_count']<=128
(root/'verification.json').write_text(json.dumps({'passed':True,'model_arms':120,'retained_equivalence_arms':40,'outcome_conservation_arms':80,'tests':outputs},indent=2)+'\n')
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='manifest.json'}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print((root/'verification.json').read_text())
