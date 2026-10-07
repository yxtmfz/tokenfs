#!/usr/bin/env python3
"""Explicit collector only. Preserve stopped evidence including SQLite sidecars.

No checkpoint, unlink, retry, kill, or server filesystem mutation. Stream a full
archive; the analyzer separately rejects sidecars instead of deleting them.
"""
import argparse,hashlib,json,shlex,subprocess,time
from pathlib import Path
REMOTE_SCRIPT=r'''
import os,subprocess,sys,tarfile
from pathlib import Path
root=Path(sys.argv[1])
if not root.is_absolute() or not root.is_dir():raise SystemExit('absolute existing evidence directory required')
p=subprocess.run(['pgrep','-u',str(os.getuid()),'-x','tokenfs'],capture_output=True,text=True)
if p.returncode!=1:raise SystemExit('TokenFS active or process check failed: refuse collection')
if not (root/'manifest.json').is_file():raise SystemExit('diagnostic manifest missing')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:archive.add(root,arcname=root.name,recursive=True)
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',required=True);p.add_argument('--remote-evidence',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 if a.host.startswith('-') or '\n' in a.host:raise ValueError('invalid SSH host')
 output=a.output.resolve()
 if output.exists():raise ValueError('refuse existing collection archive')
 output.parent.mkdir(parents=True,exist_ok=True)
 command=['ssh','-T',a.host,'python3','-c',shlex.quote(REMOTE_SCRIPT),shlex.quote(a.remote_evidence)]
 start=time.time()
 with output.open('xb') as stream:
  result=subprocess.run(command,stdout=stream,stderr=subprocess.PIPE,text=False)
 receipt={'diagnosis_only':True,'raw_sidecars_preserved':True,'server_mutation':False,'host':a.host,'remote_evidence':a.remote_evidence,'started_unix':start,'returncode':result.returncode,'archive_sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'stderr':result.stderr.decode(errors='replace')}
 output.with_suffix(output.suffix+'.receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 if result.returncode:raise SystemExit('collection failed; partial archive and receipt preserved')
 print(json.dumps(receipt))
if __name__=='__main__':main()
