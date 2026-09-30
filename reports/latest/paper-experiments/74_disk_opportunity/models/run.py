import subprocess,json
from pathlib import Path
root=Path(__file__).resolve().parent
variants=['retained','deadline','residual','renewal_window'];out=[]
for v in variants:
 subprocess.run(['c++','-std=c++17','-O2','-I',str(root/v),str(root/'replay.cpp'),'-o',str(root/v/'replay')],check=True)
for p in sorted((root/'inputs').glob('*.txt')):
 row=dict(input=p.stem,variants={})
 for v in variants:
  r=subprocess.run([str(root/v/'replay'),str(p),'prior'],check=True,capture_output=True,text=True)
  row['variants'][v]=r.stdout.splitlines()
 out.append(row)
(root/'screen.json').write_text(json.dumps(dict(speed_evidence=False,rows=out),indent=2)+'\n')
for r in out:
 print(r['input'])
 for v,lines in r['variants'].items():print(v,*[' '.join(x.split()[:3]) for x in lines])
