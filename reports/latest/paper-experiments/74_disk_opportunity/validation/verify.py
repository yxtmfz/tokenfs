import hashlib,json,math,shutil,subprocess,sys,tarfile,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve()
manifest=root/'archive-manifest.json'
if manifest.exists():
 for p,h in json.loads(manifest.read_text()).items():assert hashlib.sha256((root/p).read_bytes()).hexdigest()==h,p
with tempfile.TemporaryDirectory() as t:
 tmp=Path(t);src=tmp/'source';src.mkdir()
 with tarfile.open(root/'provenance/source.tar.gz') as a:a.extractall(src)
 freeze=json.loads((root/'data/provenance/freeze.json').read_text())
 for p,h in freeze['source_hashes'].items():assert hashlib.sha256((src/p).read_bytes()).hexdigest()==h,p
 sys.path.insert(0,str(src/'scripts'))
 import integrated_hpj_disk_opportunity_study as s
 
 # Closed, checkpointed evidence archives only: never use immutable on live WALs.
 import sqlite3
 import tail_diagnostic_analysis as diagnostic
 from contextlib import closing
 def archive_access_metrics(case):
  assert not list(Path(case).glob('state.db-*'))
  with closing(sqlite3.connect((Path(case)/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
   return ({(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')},dict(db.execute('SELECT name,value FROM metrics')))
 diagnostic.read_access_metrics=archive_access_metrics
 assert set(s.SOURCES)==set(freeze['source_hashes'])
 shutil.copytree(root/'data',tmp/'data')
 run=tmp/'data/development';original_comp=json.loads((run/'comparisons.json').read_text());original_summary=json.loads((run/'summary.json').read_text())
 m=json.loads((run/'manifest.json').read_text());assert m['source_hashes']==freeze['source_hashes']
 assert m['binary_sha256']==freeze['binary_sha256']
 assert m['spec']==s.expected_spec();assert s.sha(src/'study-configs/disk-opportunity-development.json')==freeze['specs']['development']
 audit=s.audit(run);assert audit['passed'] and audit['checked_runs']==24,audit
 # report is recalculated only on the temporary copy; raw evidence stays immutable.
 import contextlib,io
 with contextlib.redirect_stdout(io.StringIO()):s.report(run)
 assert json.loads((run/'comparisons.json').read_text())==original_comp
 assert json.loads((run/'summary.json').read_text())==original_summary
 subprocess.run([sys.executable,str(root/'validation/summarize.py'),str(run),str(tmp/'tables')],check=True,stdout=subprocess.DEVNULL)
 assert json.loads((tmp/'tables/table-values.json').read_text())==json.loads((root/'table-values.json').read_text())
 assert (tmp/'tables/tables.md').read_text()==(root/'tables.md').read_text()
 # Content-check workload is excluded from the speed table.
 content=tmp/'data/correctness';cm=json.loads((content/'manifest.json').read_text());ca=json.loads((content/'audit.json').read_text())
 assert cm['source_hashes']==freeze['source_hashes'] and cm['binary_sha256']==freeze['binary_sha256']
 assert ca['passed'] and ca['cases']==6 and ca['requests']==576
 expected=json.loads((content/'objects.json').read_text());trace=json.loads((content/'trace.json').read_text());assert len(trace)==96
 checked=0
 for name in s.VARIANTS:
  case=content/name;rows=json.loads((case/'requests.json').read_text());r=json.loads((case/'result.json').read_text())
  assert r['status']=='ok' and r['verify_every_request'] and len(rows)==96
  assert all(x['sha256']==expected[str(x['key'])] and all(x.get(k)==v for k,v in e.items()) for x,e in zip(rows,trace))
  config=s.configuration(name,Path(cm['output'])/name,Path(cm['remote_data']),24,True)
  assert json.loads((case/'config.json').read_text())==config
  assert json.loads((case/'execution.json').read_text())['binary_sha256']==(cm['reference_binary_sha256'] if name=='OldFull' else cm['binary_sha256'])
  assert not any(v for k,v in r['metrics'].items() if k.endswith('error_count'))
  checked+=len(rows)
 print(json.dumps(dict(passed=True,source_files=len(freeze['source_hashes']),speed_runs=24,speed_requests=24*1152,content_checks=checked,four_tables_exact=True)))
