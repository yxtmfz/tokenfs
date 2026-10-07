import sys,json,hashlib,random,sqlite3
from pathlib import Path
from collections import Counter
p=Path(__file__).resolve().parent;tag='integrated-hpj-cohort-calibrated';src=p/(tag+'-source');data=p/(tag+'-data');c=data/'correctness'
sys.path.insert(0,str(src/'scripts'));import integrated_hpj_cohort_calibrated_study as study
load=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
m=load(c/'manifest.json');f=load(data/'provenance/freeze.json')
assert m['stage']=='content_correctness_not_speed' and m['source_hashes']==f['source_hashes'] and m['binary_sha256']==f['binary_sha256']
assert m['driver_sha256']==sha(p/'tokenfs-eval/scripts/integrated_hpj_correctness.py')
assert m['nvme_identity']['transport']=='tcp' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(',')
events=study.trace(m['spec']);assert load(c/'trace.json')==events
expected=load(c/'objects.json')
assert expected=={str(k):hashlib.sha256(random.Random(340100000+k).randbytes(study.MIB)*2).hexdigest() for k in {e['key'] for e in events}}
assert m['variants']==study.VARIANTS and len(events)==96
for v in study.VARIANTS:
 r=load(c/v/'result.json');rows=load(c/v/'requests.json');cfg=load(c/v/'config.json');mt=r['metrics']
 assert cfg==study.configuration(v,Path(m['output'])/v,Path(m['remote_data']),24,True)
 assert r['status']=='ok' and r['verify_every_request'] and len(rows)==96
 assert all(all(row[k]==value for k,value in event.items()) and row['sha256']==expected[str(event['key'])] for row,event in zip(rows,events))
 assert r['logical_bytes']==96*2*study.MIB==mt['read_bytes']
 assert sum(mt.get('read_'+t+'_bytes',0) for t in ['remote','local','inflight'])==r['logical_bytes']
 assert mt.get('read_fill_exact_verify_count',0)==mt.get('read_fill_copy_count',0)>0
 assert mt['background_submitted']==mt['background_completed']
 assert not any(x for k,x in mt.items() if k.endswith('error_count'))
 assert all(n<=g['local_quota_mib']*study.MIB for n,g in zip(r['retained_cache_bytes'],cfg['gpus']))
 assert mt['read_fill_buffer_peak_bytes']<=4*study.MIB
 counts=Counter((f"/gpu0/shard-{x['key']:06d}.tokens",x['caller']) for x in rows)
 with sqlite3.connect((c/v/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True) as db:
  assert dict(db.execute('SELECT name,value FROM metrics'))==mt
  assert {(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}==dict(counts)
a=dict(passed=True,cases=5,requests=480,all_returned_content_sha256_verified=True,binary_sha256=m['binary_sha256'],speed_evidence=False)
(p/'cohort-calibrated-hpj-correctness-review.json').write_text(json.dumps(a,indent=2)+'\n');print(json.dumps(a))
