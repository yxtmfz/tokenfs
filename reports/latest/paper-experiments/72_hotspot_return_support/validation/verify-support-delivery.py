from pathlib import Path
import json,sys,hashlib,tarfile,tempfile,shutil,subprocess
root=Path(sys.argv[1]).resolve();tag='integrated-hpj-cohort-caller-support'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
checks=0
for line in (root/'SHA256SUMS').read_text().splitlines():
 h,name=line.split('  ',1);assert sha(root/name)==h,name;checks+=1
with tempfile.TemporaryDirectory(prefix='support-hpj-replay-') as t:
 p=Path(t)
 for archive,name in [('provenance/candidate-source.tar.gz',tag+'-source'),('raw/cn7-evidence.tar.gz',tag+'-data'),('provenance/report70-source.tar.gz','retained-source')]:
  d=p/name;d.mkdir()
  with tarfile.open(root/archive) as tf:tf.extractall(d,filter='data')
 f=load(root/'provenance/freeze.json');old=load(root/'provenance/report70-freeze.json')
 assert old['binary_sha256']=='b09253aa1577e6104421b797641b8952bd151c988eb3d9bef562b82d210cde37'
 for name,h in old['source_hashes'].items():assert sha(p/'retained-source'/name)==h
 for name,h in f['source_hashes'].items():assert sha(p/(tag+'-source')/name)==h
 changed=[str(a.relative_to(p/'retained-source')) for a in (p/'retained-source/src').rglob('*') if a.is_file() and sha(a)!=sha(p/(tag+'-source')/a.relative_to(p/'retained-source'))]
 assert sorted(changed)==['src/main.cpp','src/measured_policy.h'],changed
 shutil.copy2(root/'provenance/build.json',p/(tag+'-build.json'))
 for s in ['review-support-hpj.py','review-support-correctness.py','summarize-support-hpj.py']:
  shutil.copy2(root/'validation'/s,p/s);args=[sys.executable,str(p/s)]
  if s.startswith('review'):args.append(tag)
  run=subprocess.run(args,text=True,capture_output=True);assert run.returncode==0,(s,run.stderr[-2000:])
 assert load(p/'support-hpj-summary.json')==load(root/'rollup.json')
 assert load(p/(tag+'-correctness-review.json'))==load(root/'validation/content-review.json')
 review=load(p/(tag+'-review.json'));assert review==load(root/'validation/data-review.json')
 print(json.dumps(dict(passed=True,files_hashed=checks,source_files_verified=len(f['source_hashes']),only_production_change=changed,timed_runs=review['batch']['checked_runs'],timed_requests=review['requests'],content_requests=288,strict_hotspot_passes=load(root/'rollup.json')['strict_hotspot_passes'],strict_retained_binary_passes=load(root/'rollup.json')['strict_retained_binary_passes']),indent=2))
