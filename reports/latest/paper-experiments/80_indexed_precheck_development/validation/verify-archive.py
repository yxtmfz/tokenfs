#!/usr/bin/env python3
"""Verify an actual batch80 report without rerunning models or benchmarks."""
from pathlib import Path
import csv,hashlib,importlib.util,json,sys,tarfile
sys.dont_write_bytecode=True
root=Path(__file__).resolve().parents[1]
sha=lambda b:hashlib.sha256(b).hexdigest()
load=lambda p:json.loads(p.read_text())
def hashes(folder):return {str(p.relative_to(folder)):sha(p.read_bytes()) for p in sorted(folder.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
def tar_hashes(path):
    result={}
    with tarfile.open(path) as handle:
        for member in handle.getmembers():
            name=Path(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts and member.name not in result
            result[member.name]=sha(handle.extractfile(member).read())
    return result
actual=hashes(root);actual.pop('archive-manifest.json')
assert actual==load(root/'archive-manifest.json')['files']
for name,receipt in load(root/'provenance/archive-hashes.json')['archives'].items():
    data=(root/'provenance'/name).read_bytes();assert len(data)==receipt['bytes'] and sha(data)==receipt['sha256']
assert sha((root/'provenance/source.tar.gz').read_bytes())=='f6691da87b5cf91edc594cad618562f77f0de5fb8a6060fb395f69fc64bfbd45'
raw=hashes(root/'data')
assert raw==load(root/'provenance/data-hashes.json')==tar_hashes(root/'provenance/evidence.tar.gz')
assert raw==load(root/'validation/results/evidence-hashes.json')
source=load(root/'provenance/source-hashes.json')
assert source==tar_hashes(root/'provenance/source.tar.gz')==load(root/'data/provenance/freeze.json')['source_hashes'] and len(source)==355
spec=importlib.util.spec_from_file_location('archive_v80',root/'validation/verify80.py')
v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
sidecars=v.verify_sqlite_preservation(root/'data');assert sidecars['databases']==30
indexed=0;unindexed=0
for database in (root/'data').rglob('state.db'):
    case=database.parent;_,metrics=v.archived_sql(case);result=load(case/'result.json');cfg=load(case/'config.json')
    assert metrics==result['metrics'] and result['metrics_snapshot']=='after_daemon_shutdown'
    assert metrics['read_release_count']==metrics['read_open_count']==len(load(case/'requests.json'))
    assert metrics.get('background_submitted',0)==metrics.get('background_completed',0)
    v.verify_precheck_activity(metrics,cfg,result['verify_every_request'],case)
    if v.verify_index_schema(case,cfg):indexed+=1
    else:unindexed+=1
assert (indexed,unindexed)==(20,10)
manifest=load(root/'data/development/manifest.json');checked=0
for block in manifest['spec']['blocks']:
    for arm in block['variants']:
        case=root/'data/development'/block['id']/arm
        v.verify_environment(load(case/'environment.json'),manifest['spec']['cpu_affinity'],0,case);checked+=1
assert checked==24
review=load(root/'validation/results/review.json');pairs=load(root/'validation/results/pairs.json')
assert review['passed'] and review['source_files']==355 and review['speed_runs']==24 and review['content_checks']==576
assert review['binary_sha256']=='f5e2981b8b4f0ce54bb2994e53998608de4cec4a3c861531e8e86e0aab031f71'
primary=[p for p in pairs if p['primary_comparison']]
implementation=[p for p in pairs if p['baseline']=='NoIndexedPrecheck']
assert len(pairs)==20 and len(primary)==16 and len(implementation)==4
primary_passed=sum(p['full_acceptance'] for p in primary)
index_passed=sum(p['full_acceptance'] for p in implementation)
assert review['full_acceptance_primary']==primary_passed and review['primary_all_passed']==(primary_passed==16)
assert review['full_acceptance_indexed_precheck']==index_passed
assert load(root/'validation/results/strict-primary.json')['passed']==(primary_passed==16)
agreement=load(root/'validation/independent-review-agreement.json')
assert agreement['passed'] and agreement['byte_identical'] and len(agreement['outputs'])==8
for name,receipt in agreement['outputs'].items():
    assert receipt['root_sha256']==receipt['independent_sha256']==sha((root/'validation/results'/name).read_bytes())
ancillary=load(root/'provenance/ancillary-files.json')
for name in ['local-harness','index-independent-review','tail79-readonly','planning-cost-review']:
    copied=hashes(root/'diagnostics'/name);assert copied==ancillary[name]['hashes']
    assert all(Path(p).suffix in ['.cpp','.h','.py','.json','.txt','.tsv','.md','.log'] for p in copied)
for path in [root/'diagnostics/local-harness/source-hashes.json',root/'diagnostics/local-harness/reviewed-files.json',root/'diagnostics/index-independent-review/final-source-identity.json']:
    assert all(source[name]==h for name,h in load(path).items())
assert 'PASS: real TokenFS/MetadataStore 80 indexed precheck' in (root/'diagnostics/local-harness/run.log').read_text()
sql_proof=load(root/'diagnostics/index-independent-review/sql-review.json')
assert sql_proof['evidence_unchanged'] and sql_proof['real79_full_db_equivalence']['same_rows']
tail=root/'diagnostics/tail79-readonly';tail_manifest=load(tail/'manifest.json')
tail_hashes=hashes(tail);tail_hashes.pop('manifest.json');assert tail_hashes==tail_manifest['files'] and tail_manifest['source_batch']==79
tail_analysis=load(tail/'analysis.json')
assert tail_analysis['diagnosis_only'] and tail_analysis['raw_evidence_unchanged'] and tail_analysis['failed_primary_comparisons']==5
assert not tail_analysis['repeated_request_tier_mapping_available'] and not tail_analysis['per_request_physical_IO_mapping_available']
planning=load(root/'diagnostics/planning-cost-review/evidence.json')
assert all(source[path]==h for path,h in planning['source_sha256'].items())
model_name='hotspot-run-unit-review';model=root/'models'/model_name
archive=root/'provenance'/(model_name+'-source.tar.gz');receipt=load(root/'provenance'/(model_name+'-source-manifest.json'))
assert sha(archive.read_bytes())==receipt['archive_sha256']=='e7744741a4e2ac19e8235b46a5aca08454407eb87d8e468266c405fc69129e42'
copied={model_name+'/'+name:h for name,h in hashes(model).items()}
assert copied==tar_hashes(archive)=={r['path']:r['sha256'] for r in receipt['members']} and len(copied)==158
assert all(Path(p).suffix in ['.cpp','.h','.py','.json','.txt','.tsv','.md','.log'] for p in copied)
prefix_checks=0
for input_file in sorted((model/'inputs').glob('*.txt')):
    original=input_file.read_text().splitlines()
    for cutoff in [127,401,806]:
        assert (model/'prefix'/f'{input_file.stem}-{cutoff}.txt').read_text().splitlines()==original[:cutoff]
        for mode in ['original','run_units']:
            with (model/'logs'/f'{input_file.stem}-{mode}.tsv').open() as handle:full=list(csv.DictReader(handle,delimiter='\t'))
            with (model/'prefix'/f'{input_file.stem}-{cutoff}-{mode}.tsv').open() as handle:prefix=list(csv.DictReader(handle,delimiter='\t'))
            assert prefix==[r for r in full if int(r['observation'])<=cutoff]
            prefix_checks+=1
assert prefix_checks==60 and load(model/'prefix-verification.json')['arms']==240 and load(model/'verification.json')['arms']==80
extra_name='hotspot-extra-read79';extra=root/'models'/extra_name
extra_archive=root/'provenance'/(extra_name+'-source.tar.gz');extra_receipt=load(root/'provenance'/(extra_name+'-source-manifest.json'))
assert sha(extra_archive.read_bytes())==extra_receipt['archive_sha256']=='f2fe5e28a6c09615f9b19f3a1f3904f64d98cdd4e2244f0abff45e4619836327'
assert {extra_name+'/'+p:h for p,h in hashes(extra).items()}==tar_hashes(extra_archive)=={r['path']:r['sha256'] for r in extra_receipt['members']}
assert len(extra_receipt['members'])==29
extra_prefix_checks=0
for cutoff in [127,401,806]:
    assert (extra/'prefix'/f'input-{cutoff}.txt').read_text().splitlines()==(extra/'input.txt').read_text().splitlines()[:cutoff]
    for short,full_name in [('policy','probe-actions.tsv'),('probes','past-only-probes.tsv'),('sieve','PoolSIEVE1-model.tsv')]:
        with (extra/'prefix'/f'{short}-{cutoff}.tsv').open() as handle:prefix=list(csv.DictReader(handle,delimiter='\t'))
        with (extra/full_name).open() as handle:full=list(csv.DictReader(handle,delimiter='\t'))
        assert prefix==[r for r in full if int(r['observation'])<=cutoff]
        extra_prefix_checks+=1
assert extra_prefix_checks==9 and load(extra/'prefix-verification.json')['passed']
ci=load(root/'provenance/ci-receipt.json')
assert ci['request']==dict(commit_sha='bf52430e4fa5e8cd2e3fb6b024f3a73ed6f89e03',repo_full_name='yxtmfz/tokenfs')
run=ci['response']['structuredContent']['workflow_runs'][0]
assert run['id']==37622605042 and run['run_number']==113 and run['status']=='completed' and run['conclusion']=='success'
assert (root/'data/provenance/native-tests.log').read_text().count('Test Passed.')==12
assert 'Ran 166 tests' in (root/'provenance/build.log').read_text()
assert 'FROZEN_BINARY '+review['binary_sha256'] in (root/'provenance/build.log').read_text()
assert hashes(root/'data')==raw
print(json.dumps(dict(passed=True,files=len(actual),source_files=355,raw_files=len(raw),sqlite=sidecars,
    indexed_databases=indexed,unindexed_databases=unindexed,affinity_receipts=48,
    primary_passed=primary_passed,primary_total=16,index_passed=index_passed,index_total=4,
    server_content_checks=576,native_tests=12,python_tests=166,independent_outputs_identical=8,
    historical_tail_batch=79,negative_model_arms=80,model_prefix_cases=prefix_checks,
    historical_extra_read_prefix_comparisons=extra_prefix_checks)))
