#!/usr/bin/env python3
"""Verify package hashes and independently reproduce the fixed minimal study."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,tarfile,tempfile,runpy
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
with tempfile.TemporaryDirectory(prefix='tokenfs-minimal-audit-') as tmp:
 tmp=Path(tmp);data=tmp/'data';d=reports/'16_minimal_closeout'
 for host in ['cn7','cn8']:unpack(d/'raw'/f'tokenfs-paper-minimal-{host}.tar.gz',data)
 output=tmp/'audit.json'
 proc=subprocess.run([sys.executable,str(root/'scripts/paper_minimal_evidence.py'),'--data-root',str(data),'--public-source',str(source),'--output',str(output)],cwd=root,capture_output=True,text=True)
 assert proc.returncode==0,proc.stdout+proc.stderr
 audit=json.loads(output.read_text());assert audit['passed']
 analyzer=runpy.run_path(str(d/'provenance/analyze-paper-minimal-phases.py'))['analyze']
 assert analyzer(data/'cn7/paper-minimal-confirmation-01')==json.loads((d/'phase-review.json').read_text())
 audit['descriptive_phase_accounting_reproduced']=True
 tex=tmp/'tables.tex'
 subprocess.run([sys.executable,str(d/'provenance/export-paper-minimal-tex.py'),'--report',str(d),'--output',str(tex)],check=True)
 assert tex.read_bytes()==(root/'tables.tex').read_bytes()
 audit['publication_tables_reproduced']=True
 result=dict(passed=True,git_revision=manifest['git_revision'],hash_verified_files=len(manifest['files']),study=audit)
 args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(dict(passed=True,hash_verified_files=len(manifest['files']),independently_reproduced_confirmation_runs=audit['performance_runs'])))
