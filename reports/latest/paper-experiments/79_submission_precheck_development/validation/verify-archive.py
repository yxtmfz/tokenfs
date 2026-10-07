#!/usr/bin/env python3
"""Read-only inventory, raw SQL bundle, and stored model-prefix checks."""
from pathlib import Path
import csv,hashlib,importlib.util,json,sys,tarfile
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
load=lambda p:json.loads(p.read_text())
def hashes(path):return {str(p.relative_to(path)):sha(p.read_bytes()) for p in sorted(path.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
def tar_hashes(path):
    result={}
    with tarfile.open(path) as handle:
        for member in handle.getmembers():
            name=Path(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts
            assert member.name not in result
            result[member.name]=sha(handle.extractfile(member).read())
    return result
actual=hashes(root);actual.pop('archive-manifest.json')
assert actual==load(root/'archive-manifest.json')['files'],'archive manifest mismatch'
for name,receipt in load(root/'provenance/archive-hashes.json')['archives'].items():
    blob=(root/'provenance'/name).read_bytes()
    assert len(blob)==receipt['bytes'] and sha(blob)==receipt['sha256']
raw=hashes(root/'data')
assert raw==load(root/'provenance/data-hashes.json')==tar_hashes(root/'provenance/evidence.tar.gz') and len(raw)==339
source=load(root/'provenance/source-hashes.json')
assert source==tar_hashes(root/'provenance/source.tar.gz')==load(root/'data/provenance/freeze.json')['source_hashes'] and len(source)==350
spec=importlib.util.spec_from_file_location('archive_v79',root/'validation/verify79.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
sidecars=v.verify_sqlite_preservation(root/'data')
assert sidecars['databases']==30 and sidecars['sidecar_files']==48 and sidecars['empty_wal_pairs']==24
for db in (root/'data').rglob('state.db'):
    _,metrics=v.archived_sql(db.parent)
    result=load(db.parent/'result.json')
    assert metrics==result['metrics'] and result['metrics_snapshot']=='after_daemon_shutdown'
    assert metrics['read_release_count']==metrics['read_open_count']==len(load(db.parent/'requests.json'))
    assert metrics.get('background_submitted',0)==metrics.get('background_completed',0)
manifest=load(root/'data/development/manifest.json');expected=manifest['spec']['cpu_affinity']
affinity_cases=0
for block in manifest['spec']['blocks']:
    for arm in block['variants']:
        case=root/'data/development'/block['id']/arm
        v.verify_environment(load(case/'environment.json'),expected,0,case)
        v.verify_precheck_activity(load(case/'result.json')['metrics'],load(case/'config.json'),False,case)
        affinity_cases+=1
assert affinity_cases==24
for name in ['ram-value-model','public78-branch','grace-counterfactual']:
    receipt=load(root/'provenance'/(name+'-source-manifest.json'))
    archive=root/'provenance'/(name+'-source.tar.gz')
    assert sha(archive.read_bytes())==receipt['archive_sha256']
    saved=tar_hashes(archive)
    assert saved=={x['path']:x['sha256'] for x in receipt['members']}
    copied={name+'/'+p:h for p,h in hashes(root/'models'/name).items()}
    assert copied==saved and len(copied)==receipt['file_count']
    assert all(Path(p).suffix in ['.cpp','.h','.py','.json','.txt','.tsv','.md','.log'] for p in copied)
ancillary=load(root/'provenance/ancillary-files.json')
assert hashes(root/'diagnostics/local-harness')==ancillary['local-harness']['hashes']
harness=load(root/'diagnostics/local-harness/source-hashes.json')
assert all(source[path]==h for path,h in harness.items())
reviewed=load(root/'diagnostics/ram-retention-review/ram-retention-reviewed-source.json')
assert all(source[path]==h for path,h in reviewed.items())
for name in ['measured_policy.h','run_reuse.h']:
    assert sha((root/'diagnostics/precheck-bound'/name).read_bytes())==source['src/'+name]
assert (root/'diagnostics/precheck-bound/representative_upper_bound.log').read_text().strip()=='representative upper-bound equality checks=110592 passed'
prefix_checks={}
for name,modes,arm_count in [('ram-value-model',['lru','ranked','marginal'],120),('grace-counterfactual',['immediate','grace'],80)]:
    model=root/'models'/name;checked=0
    for input_file in sorted((model/'inputs').glob('*.txt')):
        original=input_file.read_text().splitlines()
        for cutoff in [127,401,806]:
            assert (model/'prefix'/f'{input_file.stem}-{cutoff}.txt').read_text().splitlines()==original[:cutoff]
            for mode in modes:
                with (model/'logs'/f'{input_file.stem}-{mode}.tsv').open() as handle:full=list(csv.DictReader(handle,delimiter='\t'))
                with (model/'prefix'/f'{input_file.stem}-{cutoff}-{mode}.tsv').open() as handle:prefix=list(csv.DictReader(handle,delimiter='\t'))
                assert prefix==[r for r in full if int(r['observation'])<=cutoff],(name,input_file.stem,cutoff,mode)
                checked+=1
    receipt=load(model/'prefix-verification.json')
    assert checked==len(modes)*30==receipt['cases'] and receipt['arms']==checked*4 and receipt['passed']
    assert load(model/'verification.json')['passed'] and load(model/'verification.json')['arms']==arm_count
    prefix_checks[name]=checked
review=load(root/'validation/results/review.json')
assert review['passed'] and review['source_files']==350 and review['speed_runs']==24 and review['content_checks']==576
assert review['full_acceptance_primary']==11 and review['primary_comparisons']==16 and not review['primary_all_passed']
assert review['full_acceptance_submission_precheck']==3
agreement=load(root/'validation/independent-review-agreement.json')
assert agreement['passed'] and agreement['byte_identical'] and len(agreement['outputs'])==8
for name,receipt in agreement['outputs'].items():
    assert receipt['root_sha256']==receipt['independent_sha256']==sha((root/'validation/results'/name).read_bytes())
ci=load(root/'provenance/ci-receipt.json')
assert ci['commit']=='34e73888406800dbd0d2d465287e04ef4059507b'
ci_run=ci['response']['structuredContent']['workflow_runs'][0]
assert ci_run['id']==37617725915 and ci_run['run_number']==111 and ci_run['status']=='completed' and ci_run['conclusion']=='success'
assert (root/'data/provenance/native-tests.log').read_text().count('Test Passed.')==12
assert 'Ran 163 tests' in (root/'provenance/build.log').read_text()
assert 'FROZEN_BINARY '+review['binary_sha256'] in (root/'provenance/build.log').read_text()
assert 'PASS: real TokenFS/MetadataStore 79 precheck tests' in (root/'diagnostics/local-harness/run.log').read_text()
assert hashes(root/'data')==raw,'raw changed during archive review'
print(json.dumps(dict(passed=True,files=len(actual),source_files=350,raw_files=339,
    sqlite=sidecars,affinity_receipts=48,precheck_activity_cases=24,
    model_prefix_checks=prefix_checks,primary_passed=11,primary_total=16,
    submission_precheck_passed=3,submission_precheck_total=4,independent_outputs_identical=8,
    property_check_receipt=110592,native_tests=12,python_tests=163,server_content_checks=576)))
