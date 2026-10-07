#!/usr/bin/env python3
"""Offline archive, sidecar, and saved model-prefix verification; no execution."""
from pathlib import Path
import sys,hashlib,json,tarfile,importlib.util,csv
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()
load=lambda p:json.loads(p.read_text())
actual={str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'archive-manifest.json' and '__pycache__' not in p.parts}
assert actual==load(root/'archive-manifest.json')['files'],'archive manifest mismatch'
for name,receipt in load(root/'provenance/archive-hashes.json')['archives'].items():
    blob=(root/'provenance'/name).read_bytes();assert len(blob)==receipt['bytes'] and sha(blob)==receipt['sha256'],name
raw={str(p.relative_to(root/'data')):sha(p.read_bytes()) for p in (root/'data').rglob('*') if p.is_file()}
assert raw==load(root/'provenance/data-hashes.json') and len(raw)==339
with tarfile.open(root/'provenance/evidence.tar.gz') as tar:
    members=[m for m in tar.getmembers() if m.isfile()];assert len(members)==len({m.name for m in members})==339
    archived={m.name:sha(tar.extractfile(m).read()) for m in members}
assert archived==raw
spec=importlib.util.spec_from_file_location('archive_v78',root/'validation/verify78.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
sidecars=v.verify_sqlite_preservation(root/'data')
stat=[json.loads(line) for line in (root/'provenance/sidecars.log').read_text().splitlines() if line.startswith('{')]
assert {x['path']:dict(bytes=x['bytes'],sha256=x['sha256']) for x in stat}==load(root/'data/provenance/sqlite-sidecars.json')['files']
for name,info in load(root/'provenance/ancillary-files.json').items():
    target=root/('models' if name=='migration-model' else 'diagnostics')/name
    copies={str(p.relative_to(target)):sha(p.read_bytes()) for p in target.rglob('*') if p.is_file()}
    assert copies==info['hashes'],name
    assert all(p.suffix in ['.cpp','.h','.py','.json','.txt','.tsv','.md','.log'] for p in target.rglob('*') if p.is_file())
model=root/'models/migration-model';results=load(model/'results.json');modes=list(results['rows'][0]['modes'])
assert len(results['rows'])==10 and len(modes)==9
checks=0
for stem in ['moving_shared-74801','public_toolagent-74802']:
    original=(model/'inputs'/(stem+'.txt')).read_text().splitlines()
    for cutoff in [127,401,806]:
        assert (model/'prefix-checks'/f'{stem}-{cutoff}.txt').read_text().splitlines()==original[:cutoff]
        for mode in modes:
            with (model/mode/(stem+'.tsv')).open() as handle:full=list(csv.DictReader(handle,delimiter='\t'))
            with (model/'prefix-checks'/f'{stem}-{cutoff}-{mode}.tsv').open() as handle:prefix=list(csv.DictReader(handle,delimiter='\t'))
            assert [r for r in full if int(r['observation'])<=cutoff]==prefix,(stem,cutoff,mode)
            checks+=1
assert checks==54 and load(model/'verification.json')['arms']==360
review=load(root/'validation/results/review.json')
assert review['passed'] and review['full_acceptance_primary']==12 and review['primary_comparisons']==16 and not review['primary_all_passed'] and review['full_acceptance_sync_submission']==4
assert sha((root/'provenance/collect-rejected.sh').read_bytes())==load(root/'validation/preaudit-review.json')['tools']['collect.sh']
harness=load(root/'diagnostics/telemetry-local/source-hashes.json');source=load(root/'provenance/source-hashes.json')
assert all(source[p]==h for p,h in harness.items())
print(json.dumps(dict(passed=True,files=len(actual),raw_files=339,sqlite=sidecars,model_prefix_checks=checks,primary_passed=12,primary_total=16,sync_passed=4,sync_total=4)))
