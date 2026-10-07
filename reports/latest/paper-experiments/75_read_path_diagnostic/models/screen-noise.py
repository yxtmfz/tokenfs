from pathlib import Path
import subprocess,json,shutil
root=Path(__file__).resolve().parent/'noise-model';root.mkdir(exist_ok=True)
repo=Path(__file__).resolve().parents[1]/'tokenfs-eval'
inputs=Path(__file__).resolve().parents[1]/'hotspot-opportunity-screen/inputs'
base=(repo/'src/measured_policy.h').read_text();replay=(Path(__file__).resolve().parents[1]/'hotspot-opportunity-screen/replay.cpp').read_text()
# Existing H, report74 H, and common (all arm) uncertainty unit adjustment.
variants={'retained':(False,''),'report74':(True,''),'retained_scaled':(False,'DiskReuseScale(o)*'),'report74_scaled':(True,'DiskReuseScale(o)*')}
rows=[]
for name,(disk,scale) in variants.items():
 d=root/name;d.mkdir(exist_ok=True);s=base
 if scale:s=s.replace('(1-temporal_strength_)*SavingRate()*','(1-temporal_strength_)*'+scale+'SavingRate()*')
 (d/'measured_policy.h').write_text(s);shutil.copy2(repo/'src/run_reuse.h',d/'run_reuse.h')
 (d/'replay.cpp').write_text(replay.replace('o.recent_value_floor=true;',f'o.disk_opportunity_value={str(disk).lower()};o.recent_value_floor=true;'))
 subprocess.run(['c++','-std=c++17','-O2','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
for p in sorted(inputs.glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 for name in variants:
  r=subprocess.run([str(root/name/'replay'),str(p),'prior'],capture_output=True,text=True,check=True)
  row['variants'][name]=r.stdout.splitlines()
 rows.append(row)
 print(p.stem)
 for name,lines in row['variants'].items():print(name,'; '.join(' '.join(s.split()[:3]) for s in lines))
(root/'screen.json').write_text(json.dumps({'speed_evidence':False,'rows':rows},indent=2)+'\n')
