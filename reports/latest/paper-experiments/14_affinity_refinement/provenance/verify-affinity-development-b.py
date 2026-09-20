from pathlib import Path
import tarfile,json,hashlib,subprocess
w=Path(__file__).resolve().parent;r=w/'affinity-development-b-source';r.mkdir(exist_ok=True)
def unpack(p,d):
 with tarfile.open(p) as t:
  for e in t.getmembers():
   q=Path(e.name);assert not q.is_absolute() and '..' not in q.parts and e.isfile()
  t.extractall(d,filter='data')
for host,h in [('cn7','6a7ff11d7f08e629c4c44c6741a9bec76e2bc4e684a220b7649168c9359b0845'),('cn8','14d1c68afdd5fbec5f85400322cfeb17150a23e95c69d2c856783af019223f69')]:
 p=w/f'tokenfs-affinity-development-b-{host}.tar.gz';assert hashlib.sha256(p.read_bytes()).hexdigest()==h
 unpack(p,w/'affinity-development-b-data')
unpack(w/'affinity-v2-src-02.tar.gz',r)
checks=[]
for transfer in [False,True]:
 if transfer:unpack(w/'affinity-v2-handover-controls.tar.gz',r)
 for host,names in [('cn7',['correctness','development']),('cn8',['correctness'])]:
  for short in names:
   batch=f'affinity-v2-{short}'+('-transfer' if transfer else '')+'-01';root=w/'affinity-development-b-data'/host/batch;m=json.loads((root/'manifest.json').read_text())
   for name,h in m['source_hashes'].items():assert hashlib.sha256((r/name).read_bytes()).hexdigest()==h,(batch,name)
   p=subprocess.run([str(w/'plotenv/bin/python'),'scripts/affinity_v2_study.py','audit','--output',str(root)],cwd=r,capture_output=True,text=True)
   assert p.returncode==0,p.stdout+p.stderr
   a=json.loads(p.stdout);n=(6 if short=='development' else 3) if transfer else (42 if short=='development' else 21)
   assert a['passed'] and a['checked_runs']==n
   checks.append(dict(host=host,batch=batch,cases=n,passed=True,binary_sha256=m['binary_sha256']))
result=dict(passed=True,revision='4ae4f6a485886e3f9892c4a452e44f5fa1b5b6a0',development_runs=48,content_cases=48,batches=checks)
(w/'affinity-development-b-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
