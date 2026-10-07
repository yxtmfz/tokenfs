from pathlib import Path
import json,shutil,hashlib
p=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-caller-lazy';repo=p/'tokenfs-eval';data=p/(tag+'-data');dest=repo/'reports/latest/paper-experiments/69_hotspot_direction_validation'
load=lambda f:json.loads(f.read_text())
assert load(p/(tag+'-review.json'))['passed']
assert load(p/(tag+'-correctness-review.json'))['passed']
assert load(p/'lazy-audit-rejection-tests.json')['passed']
for d in ['raw','provenance','validation']:(dest/d).mkdir(parents=True,exist_ok=True)
for n in ['manifest','batch-audit','summary','comparisons']:shutil.copy2(data/'development'/f'{n}.json',dest/f'{n}.json')
for a,b in [(tag+'-evidence.tar.gz','raw/cn7-evidence.tar.gz'),(tag+'-source.tar.gz','provenance/candidate-source.tar.gz'),('integrated-hpj-cohort-caller-source.tar.gz','provenance/retained-source.tar.gz'),(tag+'-review.json','validation/data-review.json'),(tag+'-correctness-review.json','validation/content-review.json'),('lazy-audit-rejection-tests.json','validation/audit-rejection-tests.json'),('lazy-hpj-summary.json','rollup.json'),('hotspot-headroom-analysis.json','diagnosis.json'),('hotspot-headroom-analysis.py','validation/hotspot-headroom-analysis.py'),('review-lazy-hpj.py','validation/review-lazy-hpj.py'),('review-lazy-correctness.py','validation/review-lazy-correctness.py'),('summarize-lazy-hpj.py','validation/summarize-lazy-hpj.py'),('test-lazy-audit-rejection.py','validation/test-lazy-audit-rejection.py'),('archive-lazy-hpj.py','validation/archive-lazy-hpj.py'),('verify-lazy-delivery.py','validation/verify-lazy-delivery.py'),('lazy-hpj-tables.md','tables.md'),('lazy-bound-candidate.patch','provenance/candidate.patch')]:shutil.copy2(p/a,dest/b)
for n in ['build','launch','collect','poll']:shutil.copy2(p/f'{n}-{tag}.sh',dest/f'provenance/{n}.sh')
shutil.copy2(p/'run-lazy-hpj-correctness.sh',dest/'provenance/content-check.sh')
for n in ['build','launch','collection','download']:shutil.copy2(p/f'{tag}-{n}.json',dest/f'provenance/{n}.json')
shutil.copy2(p/'integrated-hpj-cohort-caller-data/provenance/freeze.json',dest/'provenance/retained-freeze.json')
shutil.copy2(data/'provenance/freeze.json',dest/'provenance/freeze.json');shutil.copy2(data/'provenance/ctest.log',dest/'validation/ctest.log')
shutil.copy2(p/(tag+'-source/docs/'+tag+'-plan.md'),dest/'provenance/plan.md')
(dest/'SHA256SUMS').write_text(''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(dest))+'\n' for f in sorted(dest.rglob('*')) if f.is_file() and f.name!='SHA256SUMS'))
print(dest)
