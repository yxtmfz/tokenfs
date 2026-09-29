from pathlib import Path
import tempfile,tarfile,subprocess,sys,json,hashlib,shutil
root=Path(__file__).resolve().parent;report=root/'report66';tag='integrated-hpj-cohort-caller-independent'
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for line in (report/'SHA256SUMS').read_text().splitlines():
 h,p=line.split('  ',1);assert sha(report/p)==h,p
with tempfile.TemporaryDirectory(prefix='tokenfs-independent-replay-') as tmp:
 lab=Path(tmp)
 for arc,folder in [('provenance/source.tar.gz',tag+'-source'),('raw/cn7-evidence.tar.gz',tag+'-data'),('provenance/retained-source.tar.gz','retained-source')]:
  with tarfile.open(report/arc) as t:t.extractall(lab/folder,filter='data')
 source=lab/(tag+'-source');old=lab/'retained-source'
 prior=load(report/'provenance/retained-freeze.json')
 for name,h in prior['source_hashes'].items():assert sha(old/name)==h
 for p in (old/'src').rglob('*'):
  if p.is_file():assert p.read_bytes()==(source/p.relative_to(old)).read_bytes()
 assert (old/'CMakeLists.txt').read_bytes()==(source/'CMakeLists.txt').read_bytes()
 f=load(lab/(tag+'-data')/'provenance/freeze.json');assert f['binary_sha256']==prior['binary_sha256']
 # Audit the archived normalized inputs and declared disjoint source-row windows.
 origin=load(source/'study-configs/independent-hpj-public.json');used=set()
 for p in origin['prior_trace_files']:used.update(range(p['min'],p['max']+1))
 for p in (source/'study-configs').glob('*public-windows.json'):
  for win in load(p).get('windows',[]):used.update(range(win['first'],win['last']+1))
 for win in origin['windows']:
  ids=set(range(win['start'],win['end']+1));assert not used&ids;used.update(ids)
  assert len(win['events'])==1152 and all(e['source_request'] in ids and e['caller']==e['source_request']%3 for e in win['events'])
 assert origin['source_sha256']==load(report/'validation/input-origin-review.json')['source_sha256']
 for helper,args,actual,expected in [
  ('review-independent-hpj.py',[tag],tag+'-review.json','validation/independent-review.json'),
  ('review-dual-metric-correctness.py',[tag],tag+'-correctness-review.json','validation/correctness-review.json'),
  ('summarize-independent-hpj.py',[],'independent-final-summary.json','final-summary.json')]:
  shutil.copy2(report/'validation'/helper,lab/helper)
  r=subprocess.run([sys.executable,str(lab/helper),*args],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  assert load(lab/actual)==load(report/expected),helper
 s=load(report/'final-summary.json');c=load(report/'validation/correctness-review.json')
 assert s['valid_speed_runs']==34 and s['logical_requests']==39168 and c['requests']==480
 assert load(report/'validation/audit-rejection-tests.json')['passed']
 out=dict(passed=True,valid_speed_runs=34,logical_requests=39168,content_verified_requests=480,
  source_and_binary_retained=True,strict_passes=s['strict_passes'],strict_total=s['strict_total'],
  all_strict_comparisons_passed=s['all_strict_comparisons_passed'],statistical_confirmation=False,
  public_origin_local_review_verified_by_checksum=True,public_original_and_historical_bodies_rechecked_in_package=False,
  origin_note='Original public source and135 historical trace hashes were checked locally before execution; package checks the frozen derived inputs, declared disjoint rows and checksum-protected receipt, without redistributing the entire original public dataset.')
 print(json.dumps(out,indent=2))
