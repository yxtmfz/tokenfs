#!/usr/bin/env python3
"""Verify package hashes and independently reproduce BOTH confirmation studies."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tarfile,tempfile
root=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
manifest=json.loads((root/'PACKAGE-MANIFEST.json').read_text())
for name,h in manifest['files'].items():
 q=Path(name);assert not q.is_absolute() and '..' not in q.parts
 assert hashlib.sha256((root/q).read_bytes()).hexdigest()==h,name

def unpack(archive,dest):
 dest.mkdir(parents=True,exist_ok=True)
 with tarfile.open(archive) as t:
  for e in t.getmembers():
   q=Path(e.name);assert not q.is_absolute() and '..' not in q.parts and e.isfile(),e.name
  t.extractall(dest,filter='data')

reports=root/'reports/latest/paper-experiments';source=root/'public-source/toolagent_trace.jsonl'
with tempfile.TemporaryDirectory(prefix='tokenfs-bundle-audit-') as tmp:
 tmp=Path(tmp);audits={}
 for version,report in [('v3','15_affinity_handover'),('v2','14_affinity_refinement')]:
  data=tmp/(version+'-data');d=reports/report
  for host in ['cn7','cn8']:unpack(d/'raw'/f'tokenfs-affinity-{version}-{host}.tar.gz',data)
  repo=root
  if version=='v2':
   repo=tmp/'v2-frozen-source';unpack(d/'provenance/affinity-v2-src-04.tar.gz',repo);unpack(d/'provenance/affinity-v2-freeze-launch.tar.gz',repo)
  output=tmp/(version+'-audit.json')
  cmd=[sys.executable,str(repo/'scripts'/f'affinity_{version}_evidence.py'),'--data-root',str(data),'--public-source',str(source),'--output',str(output)]
  proc=subprocess.run(cmd,cwd=repo,capture_output=True,text=True)
  assert proc.returncode==0,proc.stdout+proc.stderr
  audits[version]=json.loads(output.read_text());assert audits[version]['passed']
 result=dict(passed=True,git_revision=manifest['git_revision'],hash_verified_files=len(manifest['files']),studies=audits)
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(passed=True,hash_verified_files=len(manifest['files']),independently_reproduced_confirmation_runs=sum(a['performance_runs'] for a in audits.values()))))
