#!/usr/bin/env python3
"""Offline frozen-protocol and verifier mutation checks; no performance evidence."""
import argparse,ast,copy,hashlib,importlib.util,json,os,re,shutil,sqlite3,subprocess,sys,tarfile,tempfile
from pathlib import Path

sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result
def rejects(call,fragment):
    try:call()
    except ValueError as exc:
        assert fragment in str(exc),(fragment,str(exc));return str(exc)
    raise AssertionError('mutation was not rejected: '+fragment)

def main(working_tree=None):
    v=module(ROOT/'verify80.py','independent_verify80')
    frozen=working_tree is None
    if frozen:
        hashes=read(ROOT/'source-hashes.json');before=sha(ROOT/'source.tar.gz')
    else:
        working_tree=working_tree.resolve()
        paths=['CMakeLists.txt']+sorted(str(p.relative_to(working_tree)) for directory in ['src','scripts','tests','aura_kv','study-configs','docs'] for p in (working_tree/directory).rglob('*') if p.is_file() and p.suffix in ['.cpp','.h','.py','.json','.md'] and '__pycache__' not in p.parts and not p.name.endswith('-freeze.json'))
        hashes={p:sha(working_tree/p) for p in paths};before=None
    checks=[]
    with tempfile.TemporaryDirectory(prefix='tokenfs-preaudit80-') as temporary:
        tmp=Path(temporary).resolve();src=tmp/'source';src.mkdir()
        if frozen:v.extract_source(ROOT/'source.tar.gz',src)
        else:
            for name in hashes:
                (src/name).parent.mkdir(parents=True,exist_ok=True);shutil.copy2(working_tree/name,src/name)
        actual=v.tree_hashes(src);assert actual==hashes
        sys.path.insert(0,str(src/'scripts'))
        import indexed_precheck_hpj_study as study
        assert Path(study.__file__).resolve().is_relative_to(src)
        assert set(study.SOURCES)==set(actual)
        spec=study.expected_spec()
        assert read(src/'study-configs/indexed-precheck-development.json')==spec
        assert spec['cpu_affinity']==[0,2,4,6]
        assert sum(len(b['variants']) for b in spec['blocks'])==24
        orders={b['id']:study.arm_order(b) for b in spec['blocks']}
        for scene in ['moving_shared','public_toolagent']:
            blocks=[b for b in spec['blocks'] if b['scenario']==scene]
            assert study.arm_order(blocks[0])==study.arm_order(blocks[1])[::-1]
        configs={name:study.configuration(name,Path('/case'),Path('/remote'),24,True) for name in study.VARIANTS}
        differences={name:[key for key in configs['Full']['policy'] if configs['Full']['policy'][key]!=cfg['policy'].get(key)] for name,cfg in configs.items()}
        for arm,key in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission'),('NoIndexedPrecheck','indexed_shared_precheck')]:
            assert differences[arm]==[key]
        for name,cfg in configs.items():
            assert cfg['policy']['defer_background_submission_metrics'] is True
            assert cfg['policy']['batch_background_metrics'] is True
            assert cfg['policy']['readonly_canonical'] is True
            assert cfg['policy']['precheck_shared_submission'] is True
            assert cfg['policy']['indexed_shared_precheck']==(name!='NoIndexedPrecheck')
            assert sum(g['local_quota_mib'] for g in cfg['gpus'])==24
            assert cfg['policy']['read_fill_buffer_bytes']==4*1024*1024
        environment={phase:dict(monotonic_ns=ns,cpu_affinity=[0,2,4,6]) for phase,ns in [('before',100),('after',200)]}
        assert v.verify_environment(environment,[0,2,4,6],99,'fixture')==200
        checks.append(dict(name='valid_affinity',passed=True))
        for phase in ['before','after']:
            wrong=copy.deepcopy(environment);wrong[phase]['cpu_affinity']=[0,2,4,8]
            checks.append(dict(name=phase+'_wrong_affinity',rejection=rejects(lambda:v.verify_environment(wrong,[0,2,4,6],99,'fixture'),'CPU affinity receipt mismatch')))
        checks.append(dict(name='overlapping_case',rejection=rejects(lambda:v.verify_environment(environment,[0,2,4,6],101,'fixture'),'execution order/overlap')))
        for name,cfg in configs.items():
            enabled=name!='PoolSIEVE1';indexed=name not in ['PoolSIEVE1','NoIndexedPrecheck']
            m={'submission_precheck_enabled':int(enabled),'submission_precheck_index_enabled':int(indexed),'submission_precheck_attempts':2 if enabled else 0,'submission_precheck_rejected':1 if enabled else 0}
            v.verify_precheck_activity(m,cfg,False,name)
            # Content tests must establish activation, but a short prefix may
            # legitimately not reach a complete capture or reject any task.
            prefix=dict(submission_precheck_enabled=int(enabled),submission_precheck_index_enabled=int(indexed))
            v.verify_precheck_activity(prefix,cfg,True,name)
            for counter,fragment in [('submission_precheck_index_enabled','precheck index activation'),('submission_precheck_index_fallback','precheck index fallback')]:
                bad=dict(m);bad[counter]=1-int(indexed) if counter.endswith('enabled') else 1
                checks.append(dict(name=name+'_'+counter,rejection=rejects(lambda:v.verify_precheck_activity(bad,cfg,False,name),fragment)))
            if enabled:
                checks.append(dict(name=name+'_speed_no_attempts',rejection=rejects(lambda:v.verify_precheck_activity(prefix,cfg,False,name),'precheck not exercised')))
                bad=dict(m,submission_precheck_enabled=0)
                checks.append(dict(name=name+'_content_not_activated',rejection=rejects(lambda:v.verify_precheck_activity(bad,cfg,True,name),'precheck activation')))
            else:
                bad=dict(m,submission_precheck_attempts=1)
                checks.append(dict(name=name+'_inactive_attempt',rejection=rejects(lambda:v.verify_precheck_activity(bad,cfg,False,name),'inactive precheck ran')))
        checks.append(dict(name='content_zero_attempts_all_arms_accepted',passed=True))
        checks.append(dict(name='rejections_exceed_attempts',rejection=rejects(lambda:v.verify_precheck_activity(dict(submission_precheck_enabled=1,submission_precheck_index_enabled=1,submission_precheck_attempts=1,submission_precheck_rejected=2),configs['Full'],False,'fixture'),'invalid precheck')))
        # Test the actual early verify_rows config check, before any request
        # timing can enter the verifier. This is metadata, not fake speed data.
        case=tmp/'wrong-control';case.mkdir()
        wrong=copy.deepcopy(configs['NoIndexedPrecheck']);wrong['policy']['indexed_shared_precheck']=True
        for filename,value in [('result.json',dict(status='ok',verify_every_request=False,metrics={})),('requests.json',[]),('execution.json',dict(binary_sha256='fixture')),('config.json',wrong)]:
            (case/filename).write_text(json.dumps(value))
        checks.append(dict(name='NoIndexedPrecheck_flag_mutation',rejection=rejects(lambda:v.verify_rows(case,[],{},configs['NoIndexedPrecheck'],'fixture',False),'config mismatch')))
        schema_case=tmp/'schema-fixture';schema_case.mkdir();db=sqlite3.connect(schema_case/'state.db')
        try:
            db.executescript('CREATE TABLE files(gpu_id INTEGER,physical_path TEXT,size_bytes INTEGER,tier TEXT,state TEXT); CREATE TABLE local_replicas(logical_path TEXT,gpu_id INTEGER,physical_path TEXT,size_bytes INTEGER,state TEXT);')
            db.commit()
            assert not v.verify_index_schema(schema_case,configs['NoIndexedPrecheck'])
            assert not v.verify_index_schema(schema_case,configs['PoolSIEVE1'])
            checks.append(dict(name='enabled_indexes_missing',rejection=rejects(lambda:v.verify_index_schema(schema_case,configs['Full']),'precheck index presence mismatch')))
            for name,(table,columns,predicate) in v.PRECHECK_INDEXES.items():
                db.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table}({','.join(columns)}) WHERE {predicate}")
            db.commit()
            assert v.verify_index_schema(schema_case,configs['Full'])
            checks.append(dict(name='real_partial_covering_indexes_accepted',passed=True))
            for name in ['NoIndexedPrecheck','PoolSIEVE1']:
                checks.append(dict(name=name+'_unexpected_real_index',rejection=rejects(lambda:v.verify_index_schema(schema_case,configs[name]),'precheck index presence mismatch')))
            db.execute('DROP INDEX idx_files_shared_precheck_local')
            db.execute("CREATE INDEX idx_files_shared_precheck_local ON files(gpu_id,physical_path,size_bytes) WHERE tier='local' AND state='committed'")
            db.commit()
            checks.append(dict(name='case_sensitive_predicate_mutation',rejection=rejects(lambda:v.verify_index_schema(schema_case,configs['Full']),'precheck index definition mismatch')))
            db.execute('DROP INDEX idx_files_shared_precheck_local')
            db.execute("CREATE INDEX idx_files_shared_precheck_local ON files(gpu_id,size_bytes,physical_path) WHERE tier='local' AND state='COMMITTED'")
            db.commit()
            checks.append(dict(name='covering_column_order_mutation',rejection=rejects(lambda:v.verify_index_schema(schema_case,configs['Full']),'precheck index definition mismatch')))
        finally:db.close()
        # Synthetic unit fixture ONLY: positive averages cannot override a
        # failed repeat, and the implementation diagnostic is a separate gate.
        cases={}
        for block in spec['blocks']:
            arms={}
            for name in study.VARIANTS:
                wall=9.0 if name=='Full' and block['repeat']==1 else 10.1 if name=='Full' else 10.0
                p99=.022 if name=='Full' and block['repeat']==1 else .027 if name=='Full' else .026
                arms[name]=dict(logical_bytes=2304*1024*1024,job_wall_s=wall,completed_with_background_s=wall+.001,effective_mib_s=2304/wall,request_p99_s=p99)
            cases[block['id']]=arms
        pairs,aggregates=v.build_pairs(cases)
        mechanisms=[dict(block=b['id'],strategy=n,action_sha256='Full' if n=='NoIndexedPrecheck' else n,relocated=0 if n=='NoAffinity' else 1,admissions_with_displacement=1) for b in spec['blocks'] for n in study.VARIANTS]
        source_pairs=[]
        for pair in pairs:
            changed=pair['baseline']!='NoIndexedPrecheck'
            source_pairs.append(dict(block=pair['block'],baseline=pair['baseline'],gain_pct=pair['throughput_gain_pct'],p99_change_pct=-pair['p99_reduction_pct'],drain_gain_pct=pair['drain_gain_pct'],mechanism_active=True,executed_actions_changed=changed,
              pilot_screen=study.comparison_pass(pair['baseline'],pair['throughput_gain_pct'],-pair['p99_reduction_pct'],pair['drain_gain_pct'],True,changed)))
        v.validate_acceptance(pairs,aggregates,mechanisms,source_pairs)
        assert sum(p['full_acceptance'] for p in pairs if p['primary_comparison'])==8
        assert all(a['throughput_gain_pct']>0 and a['p99_reduction_pct']>0 and a['full_acceptance_rounds']==1 and not a['all_rounds_passed'] for a in aggregates)
        assert sum(p['full_acceptance'] for p in pairs if p['baseline']=='NoIndexedPrecheck')==2
        assert not study.comparison_pass('NoHotspot',1,-1,1,True,False)
        assert not study.comparison_pass('NoIndexedPrecheck',1,-1,-1,True,False)
        checks.append(dict(name='synthetic_repeat_and_separate_control_gate',passed=True,not_performance_evidence=True))
        # Collector parses and keeps the reviewed SQL preserve/immutable rule.
        collection_reviewed=False
        for name in ['build.sh','launch.sh','collect.sh']:
            if frozen or (ROOT/name).exists():subprocess.run(['bash','-n',str(ROOT/name)],check=True)
        if frozen or (ROOT/'collect.sh').exists():
            collector=(ROOT/'collect.sh').read_text();payload=collector.split("python3 - <<'PY'\n",1)[1].rsplit('\nPY',1)[0];ast.parse(payload)
            assert "sidecar_files=len(all_sidecars)" in payload and "?mode=ro&immutable=1" in payload
            assert "assert (db.parent/'state.db-wal').stat().st_size==0" in payload
            assert "f.name in ['state.db-wal','state.db-shm']" in payload
            assert "metrics['read_release_count']==metrics['read_open_count']==len(requests)" in payload
            assert "metrics.get('background_submitted',0)==metrics.get('background_completed',0)" in payload
            collection_reviewed=True
        env=dict(os.environ,PYTHONPYCACHEPREFIX='/tmp/tokenfs-review80-pycache')
        results=[]
        for pattern in ['indexed_precheck_hpj_test.py','release_fence_test.py']:
            result=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p',pattern],cwd=src,env=env,text=True,capture_output=True)
            results.append(result.stdout+result.stderr);assert result.returncode==0
        label='preaudit' if frozen else 'working-protocol-review'
        (ROOT/(label+'-targeted-tests.log')).write_text('\n'.join(results))
        assert v.tree_hashes(src)==actual
        full_tests=None
        if frozen:
            test_log=(ROOT/'standalone-tests.log').read_text()
            match=re.search(r'Ran (\d+) tests',test_log);assert match and test_log.rstrip().endswith('OK')
            full_tests=int(match.group(1))
        summary=dict(preexecution_checks_passed=True,performance_results_reviewed=False,server_access=False,
          source_files=len(actual),source_archive_sha256=before,source_hashes_exact=True,source_is_frozen=frozen,
          frozen_spec_sha256=sha(src/'study-configs/indexed-precheck-development.json'),orders=orders,policy_differences=differences,
          cpu_affinity=dict(cpus=spec['cpu_affinity'],independent_before_after_receipt_check=True,process_inheritance='Linux subprocess inheritance; no per-thread live receipt',only_within_batch_implementation_control=True),
          checks=checks,content_prefix_zero_attempts_allowed=True,content_activation_required=True,
          index_activation_and_zero_fallback_checked=True,NoIndexedPrecheck_retains_original_precheck=True,
          actual_sqlite_index_schema_mutations_checked=True,
          all_arms_require_release_fence=True,collection_preserves_empty_wal_pairs=collection_reviewed,
          targeted_python_tests=7,full_frozen_python_tests=full_tests,
          synthetic_fixture=dict(primary_passes=8,total_primary=16,implementation_passes=2,total_implementation=4,positive_aggregate_does_not_override_failed_repeat=True,not_performance_evidence=True),
          tested_source_unchanged=True,tools={name:sha(ROOT/name) for name in ['verify80.py','preaudit80.py','build.sh','launch.sh','collect.sh','package.py'] if (ROOT/name).exists()})
    if frozen:assert sha(ROOT/'source.tar.gz')==before
    (ROOT/('preaudit-review.json' if frozen else label+'.json')).write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--working-tree',type=Path,help='Check an ephemeral working snapshot without creating/falsely claiming a frozen source package')
    main(parser.parse_args().working_tree)
