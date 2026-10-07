from pathlib import Path
import tempfile,tarfile,subprocess,sys,json,hashlib,shutil
root=Path(__file__).resolve().parent
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
reports=sorted((root/'reports').iterdir())
with tempfile.TemporaryDirectory(prefix='tokenfs-p99-replay-') as temp:
 lab=Path(temp)
 for report in reports:
  for line in (report/'SHA256SUMS').read_text().splitlines():
   h,p=line.split('  ',1);assert sha(report/p)==h,p
  tag=report.name.split('_',1)[1].replace('_','-')
  for arc,folder in [('provenance/source.tar.gz',tag+'-source'),('raw/cn7-evidence.tar.gz',tag+'-data')]:
   with tarfile.open(report/arc) as t:t.extractall(lab/folder,filter='data')
  shutil.copy2(report/'validation/review-focused-hpj.py',lab/'review-focused-hpj.py')
  subprocess.run([sys.executable,str(lab/'review-focused-hpj.py'),tag],check=True,stdout=subprocess.DEVNULL)
  assert load(lab/(tag+'-review.json'))==load(report/'validation/independent-review.json')
 new=next(p for p in reports if p.name.startswith('65_'))
 for helper,actual,expected in [('review-caller-submit-oldnew.py','caller-submit-oldnew-review.json','oldnew-review.json'),('review-caller-tail-diagnostic.py','caller-tail-diagnostic-review.json','diagnostic-review.json')]:
  if 'diagnostic' in helper:
   with tarfile.open(new/'raw/caller-tail-diagnostic-evidence.tar.gz') as t:t.extractall(lab/'caller-tail-diagnostic-data',filter='data')
  shutil.copy2(new/'validation'/helper,lab/helper)
  subprocess.run([sys.executable,str(lab/helper)],check=True,stdout=subprocess.DEVNULL)
  assert load(lab/actual)==load(new/'validation'/expected)
 pairs=load(new/'comparisons.json');oldnew=load(new/'validation/oldnew-review.json')
 assert len(pairs)==8 and sum(p['pilot_screen'] for p in pairs)==6
 assert not oldnew['both_metrics_improve_both_orders']
 decision=load(new/'decision.json');assert not decision['adopted'] and not decision['target_achieved']
 answer=dict(passed=True,new_matrix_runs=10,oldnew_control_runs=4,diagnostic_runs=2,new_matrix_requests=5760,control_requests=2304,diagnostic_requests=1152,strict_passes=6,strict_total=8,candidate_adopted=False,p99_overall_improvement_confirmed=False,baseline_retained=64,statistical_confirmation=False)
 print(json.dumps(answer,indent=2))
