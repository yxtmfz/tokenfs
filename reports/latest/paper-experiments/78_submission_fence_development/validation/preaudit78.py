#!/usr/bin/env python3
"""Local frozen-protocol audit; no server access and no performance claims."""
from pathlib import Path
import ast,hashlib,importlib.util,json,os,subprocess,sys,tarfile,tempfile

root=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def main():
    frozen=load(root/'source-hashes.json')
    with tarfile.open(root/'source.tar.gz') as t:
        members=t.getmembers();names=[m.name for m in members]
        assert len(names)==len(set(names)) and all(m.isfile() and not Path(m.name).is_absolute() and '..' not in Path(m.name).parts for m in members)
        hashes={m.name:hashlib.sha256(t.extractfile(m).read()).hexdigest() for m in members}
    assert hashes==frozen and len(hashes)==345
    source=root/'audit-source';assert all(sha(source/p)==h for p,h in frozen.items())
    sys.path.insert(0,str(source/'scripts'))
    import submission_fence_hpj_study as study
    v=module(root/'verify78.py','v78')
    expected=study.expected_spec();assert load(source/'study-configs/submission-fence-development.json')==expected
    assert sum(len(b['variants']) for b in expected['blocks'])==24
    orders={b['id']:study.arm_order(b) for b in expected['blocks']}
    for scene in ['moving_shared','public_toolagent']:
        blocks=[b for b in expected['blocks'] if b['scenario']==scene]
        assert study.arm_order(blocks[0])==study.arm_order(blocks[1])[::-1]
    cfg={n:study.configuration(n,Path('/case'),Path('/remote'),24,True) for n in study.VARIANTS}
    differences={n:[key for key in cfg['Full']['policy'] if cfg['Full']['policy'][key]!=cfg[n]['policy'].get(key)] for n in study.VARIANTS}
    assert differences['SyncSubmission']==['defer_background_submission_metrics']
    for name,c in cfg.items():assert 'defer_background_submission_metrics' in c['policy'] and c['policy']['defer_background_submission_metrics']==(name!='SyncSubmission')
    # Both aggregate rates and aggregate p99 improve in this fixture, but the
    # second round regresses. Verify that aggregate improvement cannot hide it.
    cases={}
    for b in expected['blocks']:
        arms={}
        for name in study.VARIANTS:
            wall=9.0 if name=='Full' and b['repeat']==1 else 10.1 if name=='Full' else 10.0
            p99=.022 if name=='Full' and b['repeat']==1 else .027 if name=='Full' else .026
            arms[name]=dict(logical_bytes=2304*1024*1024,job_wall_s=wall,completed_with_background_s=wall+.001,effective_mib_s=2304/wall,request_p99_s=p99)
        cases[b['id']]=arms
    pairs,aggregates=v.build_pairs(cases)
    mechanisms=[]
    for b in expected['blocks']:
        for name in study.VARIANTS:
            mechanisms.append(dict(block=b['id'],strategy=name,action_sha256='Full' if name=='SyncSubmission' else name,relocated=0 if name=='NoAffinity' else 1,admissions_with_displacement=1))
    source_pairs=[]
    for p in pairs:
        changed=p['baseline']!='SyncSubmission';active=True
        source_pairs.append(dict(block=p['block'],baseline=p['baseline'],gain_pct=p['throughput_gain_pct'],p99_change_pct=-p['p99_reduction_pct'],drain_gain_pct=p['drain_gain_pct'],mechanism_active=active,executed_actions_changed=changed,
             pilot_screen=study.comparison_pass(p['baseline'],p['throughput_gain_pct'],-p['p99_reduction_pct'],p['drain_gain_pct'],active,changed)))
    v.validate_acceptance(pairs,aggregates,mechanisms,source_pairs)
    assert sum(p['primary_comparison'] for p in pairs)==16
    assert sum(p['full_acceptance'] for p in pairs if p['primary_comparison'])==8
    assert all(a['throughput_gain_pct']>0 and a['p99_reduction_pct']>0 and a['full_acceptance_rounds']==1 and not a['all_rounds_passed'] for a in aggregates)
    assert sum(p['full_acceptance'] for p in pairs if p['baseline']=='SyncSubmission')==2
    # Execute the exact sidecar guard from the collection tool on a temporary
    # directory; no shell or remote collection command is executed here.
    collect=(root/'collect.sh').read_text();payload=collect.split("python3 - <<'PY'\n",1)[1].rsplit('\nPY',1)[0];ast.parse(payload)
    assert payload.index('sidecars=')<payload.index('with tarfile.open')
    guard='\n'.join(line for line in payload.splitlines() if line.startswith('sidecars=') or line.startswith('assert not sidecars'))
    with tempfile.TemporaryDirectory(prefix='verify78-sidecars-') as tmp:
        p=Path(tmp);exec(guard,dict(r=p));(p/'state.db-wal').write_bytes(b'pending')
        try:exec(guard,dict(r=p))
        except AssertionError:pass
        else:raise AssertionError('collection omitted sidecar')
    subprocess.run(['bash','-n',str(root/'collect.sh')],check=True)
    env=dict(os.environ,PYTHONPYCACHEPREFIX='/tmp/tokenfs-review78-pycache')
    completed=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','release_fence_test.py'],cwd=source,env=env,text=True,capture_output=True)
    (root/'preaudit-release-tests.log').write_text(completed.stdout+completed.stderr);assert completed.returncode==0
    result=dict(preexecution_checks_passed=True,performance_results_reviewed=False,server_access=False,source_files=345,
        source_archive_sha256=sha(root/'source.tar.gz'),binary_sha256_from_build_log='fa7450237ef5fc4a9291ed79f057f48bb858caed784c7ff56a454e242ae58cfe',
        frozen_spec_sha256=sha(source/'study-configs/submission-fence-development.json'),orders=orders,policy_differences=differences,
        all_arms_require_read_release_fence=True,release_count_after_fallback_submission=True,
        drain_requires_same_snapshot_release_count_and_submitted_completed=True,shutdown_io_counts_must_remain_unchanged=True,
        control_test=dict(aggregate_metrics_improved=True,individual_primary_pass_count=8,total_primary=16,aggregate_cannot_override_failed_round=True,sync_control_pass_count=2,sync_control_total=4,sync_does_not_require_changed_actions=True),
        release_fence_python_tests=4,collection_rejects_sqlite_sidecars=True,
        source_unchanged=True,tools={p.name:sha(p) for p in [root/'verify78.py',root/'collect.sh',root/'launch.sh',root/'package.py',Path(__file__)]})
    assert all(sha(source/p)==h for p,h in frozen.items())
    (root/'preaudit-review.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
