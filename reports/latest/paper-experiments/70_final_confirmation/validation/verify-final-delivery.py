from pathlib import Path
import json,sys,hashlib,tarfile,tempfile,shutil,subprocess
root=Path(sys.argv[1]).resolve();tag='integrated-hpj-cohort-caller-final'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
checks=0
for line in (root/'SHA256SUMS').read_text().splitlines():
 h,name=line.split('  ',1);assert sha(root/name)==h,name;checks+=1
subprocess.run([sys.executable,str(root/'validation/verify-final-inputs.py'),str(root)],check=True,capture_output=True,text=True)
with tempfile.TemporaryDirectory(prefix='final-hpj-replay-') as t:
 p=Path(t)
 for archive,name in [('provenance/frozen-source.tar.gz',tag+'-source'),('raw/cn7-evidence.tar.gz',tag+'-data'),('provenance/report69-source.tar.gz','retained-source')]:
  d=p/name;d.mkdir()
  with tarfile.open(root/archive) as tf:tf.extractall(d,filter='data')
 f=load(root/'provenance/freeze.json');old=load(root/'provenance/report69-freeze.json')
 assert old['binary_sha256']==f['binary_sha256']=='b09253aa1577e6104421b797641b8952bd151c988eb3d9bef562b82d210cde37'
 for name,h in old['source_hashes'].items():assert sha(p/'retained-source'/name)==h
 for name,h in f['source_hashes'].items():assert sha(p/(tag+'-source')/name)==h
 for a in (p/'retained-source/src').rglob('*'):
  if a.is_file():assert sha(a)==sha(p/(tag+'-source')/a.relative_to(p/'retained-source'))
 assert sha(p/'retained-source/CMakeLists.txt')==sha(p/(tag+'-source/CMakeLists.txt'))
 shutil.copy2(root/'provenance/build.json',p/(tag+'-build.json'))
 for s in ['review-final-hpj.py','review-final-correctness.py','summarize-final-hpj.py']:
  shutil.copy2(root/'validation'/s,p/s)
  args=[sys.executable,str(p/s)]
  if s.startswith('review'):args.append(tag)
  r=subprocess.run(args,text=True,capture_output=True)
  assert r.returncode==0,(s,r.stderr[-2000:])
 assert load(p/'final-hpj-summary.json')==load(root/'rollup.json')
 assert load(p/(tag+'-correctness-review.json'))==load(root/'validation/content-review.json')
 review=load(p/(tag+'-review.json'));assert review==load(root/'validation/data-review.json')
 print(json.dumps(dict(passed=True,files_hashed=checks,source_files_verified=len(f['source_hashes']),production_source_equals_report69=True,binary_equals_report69=True,timed_runs=review['batch']['checked_runs'],timed_requests=review['requests'],content_requests=480,strict_passes=load(root/'rollup.json')['strict_passes']),indent=2))
