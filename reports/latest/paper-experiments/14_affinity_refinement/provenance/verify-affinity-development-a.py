from pathlib import Path
import tarfile,json,hashlib,subprocess
w=Path(__file__).resolve().parent;r=w/'affinity-development-a-source';r.mkdir(exist_ok=True)
with tarfile.open(w/'affinity-v2-src-01.tar.gz') as t:
 for e in t.getmembers():
  p=Path(e.name);assert not p.is_absolute() and '..' not in p.parts and e.isfile()
 t.extractall(r,filter='data')
checks=[]
for host,names in [('cn7',['correctness','development']),('cn8',['correctness'])]:
 for short in names:
  root=w/'affinity-development-a-data'/host/f'affinity-v2-{short}-01';m=json.loads((root/'manifest.json').read_text())
  for name,h in m['source_hashes'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==h
  p=subprocess.run([str(w/'plotenv/bin/python'),'scripts/affinity_v2_study.py','audit','--output',str(root)],cwd=r,capture_output=True,text=True)
  assert p.returncode==0,p.stdout+p.stderr
  a=json.loads(p.stdout);assert a['passed'] and a['checked_runs']==(42 if short=='development' else 21)
  checks.append(dict(host=host,batch=short,cases=a['checked_runs'],passed=True,binary_sha256=m['binary_sha256']))
result=dict(passed=True,revision='0bab279ab9754b86ff12256b43a6b5eaddce7fe0',development_runs=42,content_cases=42,batches=checks)
(w/'affinity-development-a-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
