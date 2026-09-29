from pathlib import Path
import json,sys,hashlib,tarfile,tempfile,shutil,subprocess
root=Path(sys.argv[1]).resolve();tag='integrated-hpj-cohort-caller-object'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();load=lambda p:json.loads(p.read_text())
checks=0
for line in (root/'SHA256SUMS').read_text().splitlines():
 h,name=line.split('  ',1);assert sha(root/name)==h,name;checks+=1
with tempfile.TemporaryDirectory(prefix='object-hpj-replay-') as t:
 p=Path(t)
 for archive,name in [('provenance/candidate-source.tar.gz',tag+'-source'),('raw/cn7-evidence.tar.gz',tag+'-data'),('provenance/retained-source.tar.gz','retained-source')]:
  d=p/name;d.mkdir()
  with tarfile.open(root/archive) as tf:tf.extractall(d,filter='data')
 f=load(root/'provenance/freeze.json');old=load(root/'provenance/retained-freeze.json')
 assert old['binary_sha256']=='b8c9d323a658a857c0ee4b467967dbf7e24f5523bc54944a8d9710100440b4d4'
 for name,h in old['source_hashes'].items():assert sha(p/'retained-source'/name)==h
 for name,h in f['source_hashes'].items():assert sha(p/(tag+'-source')/name)==h
 # The only production modification tested is this one estimator header.
 changed=[str(a.relative_to(p/'retained-source')) for a in (p/'retained-source/src').rglob('*') if a.is_file() and sha(a)!=sha(p/(tag+'-source')/a.relative_to(p/'retained-source'))]
 assert changed==['src/run_reuse.h'],changed
 shutil.copy2(root/'provenance/build.json',p/(tag+'-build.json'))
 for s in ['review-object-hpj.py','review-object-correctness.py','summarize-object-hpj.py']:
  shutil.copy2(root/'validation'/s,p/s)
  args=[sys.executable,str(p/s)]
  if s.startswith('review'):args.append(tag)
  r=subprocess.run(args,text=True,capture_output=True)
  assert r.returncode==0,(s,r.stderr[-2000:])
 assert load(p/'object-hpj-summary.json')==load(root/'rollup.json')
 assert load(p/(tag+'-correctness-review.json'))==load(root/'validation/content-review.json')
 review=load(p/(tag+'-review.json'))
 assert review==load(root/'validation/data-review.json')
 answer=dict(passed=True,files_hashed=checks,source_files_verified=len(f['source_hashes']),old_source_files_verified=len(old['source_hashes']),only_production_candidate_change=changed,timed_runs=review['batch']['checked_runs'],timed_requests=review['requests'],content_requests=480,strict_ablation_and_sieve_passes=load(root/'rollup.json')['strict_ablation_and_sieve_passes'],strict_retained_binary_passes=load(root/'rollup.json')['strict_retained_binary_passes'])
 print(json.dumps(answer,indent=2))
