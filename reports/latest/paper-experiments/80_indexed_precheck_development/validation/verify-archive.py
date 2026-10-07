#!/usr/bin/env python3
"""Verify an actual batch80 report without rerunning models or benchmarks."""
from pathlib import Path
import csv,hashlib,importlib.util,json,math,sys,tarfile
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
# Post-benchmark trace annex: retain its distinct diagnosis-only status.
moving=root/'diagnostics/moving-trace';moving_raw=hashes(moving/'data')
assert len(moving_raw)==27 and moving_raw==tar_hashes(moving/'provenance/evidence.tar.gz')
assert sha((moving/'provenance/evidence.tar.gz').read_bytes())=='c71dec53662c741e0423814c8a8ff050a34ce97094f81dcd448d7a789e2e7fb1'
assert not list((moving/'data').rglob('state.db-*'))
trace_agreement=load(moving/'provenance/agreement.json')
assert trace_agreement['passed'] and trace_agreement['audit_json_equal'] and trace_agreement['analysis_byte_identical']
assert trace_agreement['diagnosis_only'] and not trace_agreement['performance_evidence'] and trace_agreement['requests']==2304
assert moving_raw==trace_agreement['raw_files']==load(moving/'provenance/moving-trace-inputhashes-independent.json')
assert hashes(moving/'review')==trace_agreement['analysis_files'] and len(trace_agreement['analysis_files'])==7
trace_audit=load(moving/'provenance/moving-trace-audit-root.json')
assert trace_audit==load(moving/'provenance/moving-trace-audit-independent.json')==load(moving/'data/diagnostic-audit.json')
assert trace_audit['passed'] and trace_audit['diagnosis_only'] and not trace_audit['performance_evidence']
assert trace_audit['source_files_checked']==355 and trace_audit['binary_sha256']==review['binary_sha256']
trace_source=load(moving/'data/source-freeze.json')
assert trace_source['source_hashes']==source and trace_source['binary_sha256']==review['binary_sha256']
tool_receipt=load(moving/'provenance/frozen-tools-manifest.json');tool_hashes=hashes(moving/'tools')
assert sha((moving/'provenance/frozen-tools.tar.gz').read_bytes())==tool_receipt['archive_sha256']=='540c7eddf7362313aca0dccf1b4cbe62d17e770ceb433e7503038a3f5b5c87c7'
assert tool_hashes==tar_hashes(moving/'provenance/frozen-tools.tar.gz')=={r['path']:r['sha256'] for r in tool_receipt['members']}
assert len(tool_hashes)==12 and tool_receipt['status']=='prepared_not_executed'  # preserved historical freeze
for rel,h in load(moving/'data/receipts.json')['files'].items():assert moving_raw[rel]==h
independent=moving/'independent-review';independent_manifest=load(independent/'independent-manifest.json')
independent_hashes=hashes(independent);independent_hashes.pop('independent-manifest.json')
assert independent_hashes==independent_manifest['files'] and len(independent_hashes)==10
assert independent_manifest['diagnosis_only'] and not independent_manifest['performance_evidence']
assert all(independent_hashes[name]==h for name,h in trace_agreement['analysis_files'].items())
decomposition=load(independent/'decomposition.json')
assert decomposition['diagnosis_only'] and not decomposition['performance_evidence'] and decomposition['raw_27_hashes_unchanged']
assert decomposition['request_count_per_arm']==1152 and decomposition['same_ordinal_tier_mismatches']==0
assert decomposition['same_ordinal_location_mismatches']==44 and decomposition['top12_all_first_remote']
trace_analysis=load(moving/'review/analysis.json');trace_requests={};trace_rows={};trace_results={}
for arm in ['Full','NoHotspot']:
    case=moving/'data'/arm;requests=load(case/'requests.json');trace_requests[arm]=requests
    result=load(case/'result.json');trace_results[arm]=result;cfg=load(case/'config.json')
    _,metrics=v.archived_sql(case)
    assert metrics==result['metrics'] and result['metrics_snapshot']=='after_daemon_shutdown'
    assert metrics['read_release_count']==metrics['read_open_count']==len(requests)==1152
    assert metrics.get('background_submitted',0)==metrics.get('background_completed',0)==28
    assert metrics['direct_backend_pread_ops']==696 and metrics['direct_backend_pread_bytes']==486539264
    assert metrics['read_fill_copy_count']==28 and metrics['read_fill_copy_bytes']==58720256
    assert metrics['direct_read_tail_buffer_bytes_peak']==4096
    assert not result['verify_every_request'] and all(r['sha256'] is None for r in requests)
    assert v.verify_index_schema(case,cfg)
    v.verify_precheck_activity(metrics,cfg,False,case)
    v.verify_environment(load(case/'environment.json'),[0,2,4,6],0,case)
    execution=load(case/'execution.json')
    assert execution['binary_sha256']==review['binary_sha256'] and execution['config_sha256']==moving_raw[arm+'/config.json']
    assert all(tool_hashes[name]==h for name,h in execution['driver_hashes'].items())
    with (moving/'review'/(arm+'-requests.csv')).open() as handle:rows=list(csv.DictReader(handle))
    trace_rows[arm]=rows;assert len(rows)==1152
    for i,(row,request) in enumerate(zip(rows,requests)):
        assert int(row['index'])==request['index']==i and int(row['key'])==request['key'] and int(row['caller'])==request['caller']
        assert math.isclose(float(row['response_ms']),request['response_seconds']*1000,abs_tol=1e-9)
        assert row['physical_pread_ops']==row['physical_pread_bytes']==''
    p99=sorted(requests,key=lambda r:r['response_seconds'])[math.ceil(len(requests)*.99)-1]
    assert math.isclose(p99['response_seconds'],result['request_p99_s'],abs_tol=1e-12)
    assert math.isclose(result['effective_mib_s'],sum(r['bytes'] for r in requests)/(1024**2)/result['job_wall_s'],abs_tol=1e-9)
    assert p99['index']==decomposition['p99_ordinal'][arm]
    assert math.isclose(result['request_p99_s']*1000,decomposition['p99_ms'][arm],abs_tol=1e-9)
    a=trace_analysis[arm];events=load(case/'request-trace.json')
    assert a['passed'] and a['diagnosis_only'] and not a['performance_evidence']
    assert len(events['events'])==a['event_count']==9408 and events['dropped']==a['dropped']==0
    assert len(a['top12'])==12 and a['physical_pread_ops']==696 and a['physical_pread_bytes']==486539264
    assert all(r['access_class']=='first' and r['tier']=='remote' and r['copy_pipeline_overlap_ms']==0 for r in a['top12'])
    assert all(r['physical_pread_ops'] is None and r['physical_pread_bytes'] is None for r in a['top12'])
    assert {r['index'] for r in a['top12']}=={r['index'] for r in sorted(requests,key=lambda r:r['response_seconds'],reverse=True)[:12]}
    assert {(r['access_class'],r['tier']):r['n'] for r in a['strata'] if r['n']}=={('first','remote'):67,('reused','remote'):17,('reused','local'):148,('reused','inflight'):920}
with (moving/'review/same-ordinal-all.tsv').open() as handle:same=list(csv.DictReader(handle,delimiter='\t'))
assert len(same)==1152 and all(r['left_tier']==r['right_tier'] for r in same)
assert sum(r['left_location']!=r['right_location'] for r in same)==44
assert sum(r['top12_union']=='True' for r in same)==16
for row in same:
    for side in ['left','right']:
        assert row[side+'_physical_pread_ops']==row[side+'_physical_pread_bytes']==''
wall_delta=(trace_results['Full']['job_wall_s']-trace_results['NoHotspot']['job_wall_s'])*1000
request_delta=(trace_requests['Full'][844]['response_seconds']-trace_requests['NoHotspot'][844]['response_seconds'])*1000
assert math.isclose(wall_delta,decomposition['wall_delta_ms'],abs_tol=1e-8)
assert math.isclose(request_delta,decomposition['index844_response_delta_ms'],abs_tol=1e-8)
assert math.isclose(request_delta/wall_delta,decomposition['index844_response_delta_over_wall_delta'],abs_tol=1e-9)
protected=load(moving/'provenance/protected-primary80-hashes.json')
assert len(protected)==350 and all(sha((root/rel).read_bytes())==h for rel,h in protected.items())
assert hashes(moving/'data')==moving_raw  # no SQLite or parser writes into frozen evidence
fuse=root/'diagnostics/fuse-read-review';fuse_receipt=load(fuse/'copied-files.json');fuse_hashes=hashes(fuse)
fuse_hashes.pop('copied-files.json');assert fuse_hashes==fuse_receipt['files'] and len(fuse_hashes)==8
assert fuse_receipt['no_binary_package_or_library_copied'] and fuse_receipt['no_fresh_kernel_query']
assert all(tool_hashes[name]==h for name,h in load(fuse/'moving-trace-reviewed-files.json').items())
fuse_inputs=load(fuse/'evidence.json')['inputs_sha256']
assert all(source[name[len('tokenfs-eval/'):]]==h for name,h in fuse_inputs.items() if name.startswith('tokenfs-eval/'))
assert fuse_hashes['fuse3-package/usr/include/fuse3/fuse_common.h']==fuse_inputs['hotspot-fuse-read-review/fuse3-package/usr/include/fuse3/fuse_common.h']
assert fuse_hashes['historical-affinity-shared-preflight-cn7.json']==fuse_inputs['affinity-shared-preflight-cn7.json']
assert sha((root/'provenance/build.log').read_bytes())==fuse_inputs['hotspot-indexed80/build.log']
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
    historical_extra_read_prefix_comparisons=extra_prefix_checks,
    moving_trace_diagnostic_requests=2304,moving_trace_raw_files=27,moving_trace_analysis_identical=7,
    moving_trace_frozen_tools=12,moving_trace_same_tier_requests=1152,moving_trace_changed_locations=44,
    moving_trace_diagnostic_not_performance=True,primary_protected_files=len(protected))))
