#!/usr/bin/env python3
"""Fixed two-arm public74802 trace diagnosis; never performance evidence.

Run only after the 77 speed batch finishes. Uses its exact frozen binary/source.
Does not alter source, study freezes, the primary matrix, or earlier results.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,os,random,shutil,subprocess,sys,time
from pathlib import Path

MIB=1024*1024
ORDER=['Full','NoHotspot']
SPEC=dict(scenario='public_toolagent',seed=74802,requests=1152,shard_mib=2,quota_mib=24)

def require(value,message):
    if not value:raise ValueError(message)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def dump(path,value):Path(path).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def source_modules(source):
    source=source.resolve();sys.path.insert(0,str(source/'scripts'))
    import object_cohort_hpj_study as study
    import evidence_benchmark as benchmark
    require(Path(study.__file__).resolve().parents[1]==source,'source import provenance')
    return study,benchmark

def driver_receipts():
    root=Path(__file__).resolve().parent
    return {name:sha(root/name) for name in ['tail-trace.py','tail-trace-analysis.py']}

def validate_source(source,diagnostic_freeze):
    frozen=read(diagnostic_freeze);study,benchmark=source_modules(source)
    hashes={p:sha(source/p) for p in study.SOURCES}
    require(hashes==frozen['source_hashes'],'diagnostic/source freeze mismatch')
    require(driver_receipts()==frozen['driver_hashes'],'diagnostic driver freeze mismatch')
    require(frozen['spec']==SPEC and frozen['order']==ORDER and frozen['diagnosis_only'] is True,'diagnostic protocol freeze')
    events=study.trace(SPEC)
    require(len(events)==1152 and all(e['bytes']==2*MIB and e['index']==i for i,e in enumerate(events)),'full trace shape')
    require(digest(events)==frozen['trace_sha256'],'trace freeze mismatch')
    return study,benchmark,frozen,events

def config(study,name,case,data):
    cfg=study.configuration(name,case,data,24,True)
    cfg['policy']['request_trace_path']=str(case/'request-trace.json')
    cfg['policy']['profile_control_path']=True
    return cfg

def expected_objects(events):
    return {str(key):hashlib.sha256(random.Random(SPEC['seed']*100000+key).randbytes(MIB)*2).hexdigest()
            for key in sorted({e['key'] for e in events})}

def audit(root,source,diagnostic_freeze):
    study,benchmark,frozen,events=validate_source(source,diagnostic_freeze);m=read(root/'manifest.json')
    require(m['diagnosis_only'] is True and m['performance_evidence'] is False and m['verify_every_request'] is False,'diagnostic classification')
    require(m['spec']==SPEC and m['order']==ORDER,'fixed protocol')
    require(m['source_hashes']==frozen['source_hashes'] and m['binary_sha256']==frozen['binary_sha256'],'provenance')
    require(m['driver_hashes']==driver_receipts() and m['diagnostic_freeze_sha256']==sha(diagnostic_freeze),'driver provenance')
    sourcefreeze=read(root/'source-freeze.json')
    require(sourcefreeze['source_hashes']==m['source_hashes'] and sourcefreeze['binary_sha256']==m['binary_sha256'],'original source/binary receipt')
    require(sourcefreeze['specs']['development']==sha(source/'study-configs/object-cohort-development.json'),'original speed spec hash')
    require(read(root/'trace.json')==events and read(root/'objects.json')==expected_objects(events),'frozen data/objects')
    require(read(root/'input.json')==dict(spec=SPEC,order=ORDER,trace_sha256=digest(events),objects_sha256=digest(expected_objects(events))),'input receipt')
    analyzer=module(Path(__file__).with_name('tail-trace-analysis.py'),'trace_analysis')
    checks={}
    for name in ORDER:
        case=root/name;cfg=config(study,name,Path(m['output'])/name,Path(m['remote_data']))
        require(read(case/'config.json')==cfg,'exact diagnostic configuration '+name)
        execution=read(case/'execution.json')
        require(execution==dict(binary_sha256=m['binary_sha256'],source_hashes_sha256=digest(m['source_hashes']),config_sha256=sha(case/'config.json'),driver_hashes=driver_receipts()),'execution receipt '+name)
        rows=read(case/'requests.json');result=read(case/'result.json')
        require(len(rows)==1152 and all(all(row.get(k)==v for k,v in event.items()) for row,event in zip(rows,events)),'complete request order '+name)
        require(result['strategy']==name,'strategy name')
        require(sum(result['retained_cache_bytes'])<=24*MIB,'aggregate retention')
        require(all(v<=g['local_quota_mib']*MIB for v,g in zip(result['retained_cache_bytes'],cfg['gpus'])),'per-domain retention')
        require(result['verified_replicas']>0,'retained content validation missing')
        details=analyzer.analyze_case(case)
        checks[name]={k:details[k] for k in ['passed','requests','event_count','dropped','top_count','physical_pread_ops','physical_pread_bytes','extra_tail_buffer_bytes_peak']}
    require(not list(root.rglob('failure.json')),'failed attempt present')
    actual={p.parent.name for p in root.glob('*/result.json')};require(actual==set(ORDER),'unexpected case')
    return dict(passed=True,diagnosis_only=True,performance_evidence=False,arms=checks,
                source_files_checked=len(m['source_hashes']),binary_sha256=m['binary_sha256'],
                limitation='No per-request content hash; run_case validates retained replicas after timing. Trace durations are diagnostic only.')

def run(args):
    source=args.source_root.resolve();study,benchmark,frozen,events=validate_source(source,args.diagnostic_freeze)
    binary=args.binary.resolve();original=read(args.freeze)
    require(sha(binary)==frozen['binary_sha256']==original['binary_sha256'],'exact 77 binary required')
    require(original['source_hashes']==frozen['source_hashes'],'original source freeze')
    require(original['specs']['development']==sha(source/'study-configs/object-cohort-development.json'),'original development spec')
    require('CMAKE_BUILD_TYPE:STRING=Release' in (binary.parent/'CMakeCache.txt').read_text(),'Release build required')
    p=subprocess.run(['pgrep','-u',str(os.getuid()),'-x','tokenfs'],capture_output=True,text=True)
    require(p.returncode==1,'TokenFS already running or process check failed; diagnostic must be serial')
    from measured_study import check_mount
    identity=check_mount(args.remote_root.resolve(),False)
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    data=args.remote_root.resolve()/('trace77-'+root.name);data.mkdir(exist_ok=False)
    (data/'gpu0').mkdir()
    manifest=dict(diagnosis_only=True,performance_evidence=False,verify_every_request=False,
                  spec=SPEC,order=ORDER,source_hashes=frozen['source_hashes'],binary_sha256=sha(binary),
                  driver_hashes=driver_receipts(),diagnostic_freeze_sha256=sha(args.diagnostic_freeze),
                  source_archive_sha256=frozen['source_archive_sha256'],source_root=str(source),output=str(root),remote_data=str(data),
                  backend_direct=True,created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
                  topology='cn7 three logical GPU domains, cn13 remote NVMe/TCP; no physical GPU claim',**identity)
    dump(root/'manifest.json',manifest);shutil.copyfile(args.freeze,root/'source-freeze.json')
    dump(root/'trace.json',events)
    expected=expected_objects(events);dump(root/'objects.json',expected)
    dump(root/'input.json',dict(spec=SPEC,order=ORDER,trace_sha256=digest(events),objects_sha256=digest(expected)))
    try:
        for key in sorted(map(int,expected)):
            path=data/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(SPEC['seed']*100000+key).randbytes(MIB)
            with path.open('xb') as handle:handle.write(payload*2);handle.flush();os.fsync(handle.fileno())
            require(sha(path)==expected[str(key)],'canonical content')
        for name in ORDER:
            case=root/name;cfg=config(study,name,case,data)
            before=study.environment()
            benchmark.run_case(binary,case,data,name,events,expected,24,False,True,configuration=cfg)
            require(sha(binary)==manifest['binary_sha256'],'binary changed during run')
            dump(case/'execution.json',dict(binary_sha256=sha(binary),source_hashes_sha256=digest(manifest['source_hashes']),config_sha256=sha(case/'config.json'),driver_hashes=driver_receipts()))
            dump(case/'environment.json',dict(before=before,after=study.environment()))
            print(json.dumps(dict(diagnosis_only=True,strategy=name,completed=True,requests=1152)),flush=True)
        review=audit(root,source,args.diagnostic_freeze);dump(root/'diagnostic-audit.json',review)
        files={str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file() and
               (p.suffix in ['.json','.db','.log'] or p.name=='state.db')}
        dump(root/'receipts.json',dict(diagnosis_only=True,files=files))
        shutil.rmtree(data)
        print(json.dumps(review),flush=True)
    except Exception as exc:
        dump(root/'failure.json',dict(error=repr(exc),diagnosis_only=True));raise

def selftest(args):
    study,benchmark,frozen,events=validate_source(args.source_root.resolve(),args.diagnostic_freeze)
    full=config(study,'Full',Path('/PLAN/Full'),Path('/PLAN/remote'))
    noh=config(study,'NoHotspot',Path('/PLAN/Full'),Path('/PLAN/remote'))
    diffs={k:(full['policy'].get(k),noh['policy'].get(k)) for k in full['policy'] if full['policy'].get(k)!=noh['policy'].get(k)}
    analyzer=module(Path(__file__).with_name('tail-trace-analysis.py'),'trace_analysis')
    require(analyzer.union_ns(10,30,[(0,12),(11,15),(20,40)])==15,'overlap union selftest')
    require(analyzer.union_ns(10,30,[(30,40)])==0,'async after-close clipping')
    require(len(expected_objects(events))>0,'objects')
    return dict(passed=True,diagnosis_only=True,executed=False,source_files=len(frozen['source_hashes']),requests=len(events),
                arms=ORDER,policy_differences=diffs,binary_bound=frozen['binary_sha256'],objects=len(expected_objects(events)))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=['run','audit','selftest'])
    p.add_argument('--source-root',type=Path,required=True);p.add_argument('--diagnostic-freeze',type=Path,required=True)
    for name in ['binary','freeze','output','remote-root']:p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    if a.operation=='run':run(a)
    elif a.operation=='audit':print(json.dumps(audit(a.output.resolve(),a.source_root.resolve(),a.diagnostic_freeze)))
    else:print(json.dumps(selftest(a)))
