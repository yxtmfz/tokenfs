from pathlib import Path
from contextlib import closing
import json,sys,sqlite3,hashlib

root=Path(__file__).resolve().parent
source=root/'integrated-hpj-cohort-calibrated-source'
data=root/'cohort-tail-diagnostic-data'
sys.path.insert(0,str(source/'scripts'))
import integrated_hpj_cohort_calibrated_study as study
import tail_diagnostic_analysis as diagnostic
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=load(data/'manifest.json')
assert manifest['diagnostic_only'] and not manifest['speed_evidence']
assert manifest['binary_sha256']=='0cf7eb8361a797063ad05212a9cd65fad77ad2ad09674c6f2c6e987a90431cd8'
for p,h in manifest['source_hashes'].items():assert sha(source/p)==h
assert manifest['nvme_identity']['transport']=='tcp'
assert 'traddr=28.10.10.13' in manifest['nvme_identity']['address'].split(',')
trace=study.trace(manifest['spec']);assert load(data/'trace.json')==trace
assert manifest['variants']==['Full','PoolSIEVE1']
def read_metrics(case):
    assert not list(Path(case).glob('state.db-*'))
    with closing(sqlite3.connect((Path(case)/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
        return ({(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')},dict(db.execute('SELECT name,value FROM metrics')))
diagnostic.read_access_metrics=read_metrics
archived=load(data/'diagnosis.json');out=[]
for v in manifest['variants']:
    cfg=load(data/v/'config.json');case=Path(cfg['filesystem']['mount_point']).parent
    expected=study.configuration(v,case,Path(manifest['remote_data']),24,True)
    expected['policy']['request_trace_path']=str(case/'request-trace.json')
    assert cfg==expected
    requests=load(data/v/'requests.json')
    assert len(requests)==len(trace)==576
    assert all(all(row[k]==value for k,value in event.items()) for row,event in zip(requests,trace))
    result=diagnostic.analyze_case(data/v);result['strategy']=v
    assert result==next(x for x in archived['runs'] if x['strategy']==v)
    out.append(dict(strategy=v,requests=result['requests'],events=result['event_count'],passed=True,
                    tail_tiers=[x['tier'] for x in result['tail_requests']]))
review=dict(passed=True,speed_evidence=False,source_files_verified=len(manifest['source_hashes']),runs=out)
(root/'cohort-tail-diagnostic-review.json').write_text(json.dumps(review,indent=2)+'\n')
print(json.dumps(review))
