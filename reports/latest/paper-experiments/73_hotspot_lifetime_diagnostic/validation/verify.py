import hashlib,json,sqlite3,sys,tarfile,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve()
for p,h in json.loads((root/'archive-manifest.json').read_text()).items():
 assert hashlib.sha256((root/p).read_bytes()).hexdigest()==h,p
sys.path.insert(0,str(root/'validation'))
from hotspot_lifetime_analysis import analyze_case
summary=json.loads((root/'data/lifetime-summary.json').read_text())
manifest=json.loads((root/'data/manifest.json').read_text())
with tempfile.TemporaryDirectory() as temp:
 with tarfile.open(root/'provenance/source.tar.gz') as t:t.extractall(temp)
 src=Path(temp)
 for p,h in manifest['source_hashes'].items():assert hashlib.sha256((src/p).read_bytes()).hexdigest()==h,p
 sys.path.insert(0,str(src/'scripts'))
 from integrated_hpj_cohort_caller_final_study import configuration,trace
 cases=sorted((root/'data').glob('*/*/result.json'));assert len(cases)==4
 for path in cases:
  case=path.parent;key=str(case.relative_to(root/'data'))
  assert analyze_case(case)==summary[key]
  r=json.loads(path.read_text());requests=json.loads((case/'requests.json').read_text());cfg=json.loads((case/'config.json').read_text())
  scene=case.parent.name;seed=74801 if scene=='moving_shared' else 74802
  expected=trace(dict(scenario=scene,seed=seed,requests=1152,shard_mib=2))
  assert json.loads((case.parent/'trace.json').read_text())==expected
  assert len(requests)==1152 and all(all(row.get(k)==v for k,v in e.items()) for row,e in zip(requests,expected))
  assert r['logical_bytes']==sum(x['bytes'] for x in requests)==sum(summary[key]['bytes_by_tier'].values())
  assert abs(r['effective_mib_s']-r['logical_bytes']/1048576/r['job_wall_s'])<1e-9
  assert r['request_p99_s']==sorted(x['response_seconds'] for x in requests)[1140]
  db=sqlite3.connect((case/'state.db').as_uri()+'?immutable=1',uri=True);assert dict(db.execute('SELECT name,value FROM metrics'))==r['metrics']
  db.row_factory=sqlite3.Row
  assert [dict(x) for x in db.execute('SELECT * FROM policy_events ORDER BY seq')]==json.loads((case/'policy-events.json').read_text())
  db.close()
  assert r['metrics']['background_submitted']==r['metrics']['background_completed']
  assert not any(v for k,v in r['metrics'].items() if k.endswith('error_count'))
  assert sum(r['retained_cache_bytes'])<=24*1048576
  assert all(n<=g['local_quota_mib']*1048576 for n,g in zip(r['retained_cache_bytes'],cfg['gpus']))
  assert r['metrics']['read_fill_buffer_peak_bytes']<=4*1048576
  # Configuration paths differ per case; all policy settings except the H
  # switch must match within a paired scene.
  other=case.parent/('NoHotspot' if case.name=='Full' else 'Full')/'config.json'
  a=cfg['policy'].copy();b=json.loads(other.read_text())['policy'].copy()
  assert a.pop('measured_static_reuse_value')==(case.name=='NoHotspot')
  b.pop('measured_static_reuse_value');a.pop('request_trace_path');b.pop('request_trace_path');assert a==b
  assert not summary[key]['unmatched_local_handles']
print(json.dumps(dict(passed=True,runs=4,requests=4608,source_files=len(manifest['source_hashes']),dropped_events=0,unmatched_local_reads=0)))
