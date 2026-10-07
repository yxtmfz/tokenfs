from pathlib import Path
import subprocess,json,hashlib
r=Path(__file__).resolve().parent
variants=['disk_clock_raw','disk_clock_matched','logical_clock_raw','logical_clock_matched','disk_clock_persistent_raw','disk_clock_persistent_matched','logical_clock_persistent_raw','logical_clock_persistent_matched']
results=[]
for v in variants:
 for f in ['verify.cpp']+(['verify-persistent.cpp'] if 'persistent' in v else []):
  exe=r/v/f.replace('.cpp','');subprocess.run(['c++','-std=c++17','-O2','-I',str(r/v),str(r/f),'-o',str(exe)],check=True)
  p=subprocess.run([str(exe),'logical' if v.startswith('logical') else 'disk'],check=True,text=True,capture_output=True);results.append({'variant':v,'test':f,'stdout':p.stdout.strip()})
result={'passed':True,'tests':results,'baseline_header_sha256':hashlib.sha256((r/'retained/measured_policy.h').read_bytes()).hexdigest()}
(r/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
