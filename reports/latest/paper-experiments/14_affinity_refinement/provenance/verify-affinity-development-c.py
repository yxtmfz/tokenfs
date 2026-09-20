from pathlib import Path
import tarfile,json,hashlib,subprocess
w=Path(__file__).resolve().parent;r=w/'affinity-development-c-source';r.mkdir(exist_ok=True)
def unpack(p,d):
 with tarfile.open(p) as t:
  for e in t.getmembers():
   q=Path(e.name);assert not q.is_absolute() and '..' not in q.parts and e.isfile()
  t.extractall(d,filter='data')
for host in ['cn7','cn8']:
 p=w/f'tokenfs-affinity-development-c-{host}.tar.gz';m=json.loads((w/f'affinity-development-c-{host}-manifest.json').read_text());assert hashlib.sha256(p.read_bytes()).hexdigest()==m['sha256']
 unpack(p,w/'affinity-development-c-data')
unpack(w/'affinity-v2-src-03.tar.gz',r)
checks=[]
for host,names in [('cn7',['correctness','development']),('cn8',['correctness'])]:
 for short in names:
  root=w/'affinity-development-c-data'/host/f'affinity-v2-{short}-01';m=json.loads((root/'manifest.json').read_text())
  for name,h in m['source_hashes'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==h
  p=subprocess.run([str(w/'plotenv/bin/python'),'scripts/affinity_v2_study.py','audit','--output',str(root)],cwd=r,capture_output=True,text=True)
  assert p.returncode==0,p.stdout+p.stderr
  a=json.loads(p.stdout);n=48 if short=='development' else 24;assert a['passed'] and a['checked_runs']==n
  checks.append(dict(host=host,batch=short,cases=n,passed=True,binary_sha256=m['binary_sha256']))
result=dict(passed=True,revision='87232a47c55883c8ce45171ead8c15eabbbf730c',development_runs=48,content_cases=48,batches=checks)
(w/'affinity-development-c-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
