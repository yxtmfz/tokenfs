import copy,json,shutil,sqlite3,sys,tarfile,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve();tests=[]
with tempfile.TemporaryDirectory() as t:
 tmp=Path(t);src=tmp/'source';src.mkdir()
 with tarfile.open(root/'provenance/source.tar.gz') as a:a.extractall(src)
 sys.path.insert(0,str(src/'scripts'));import integrated_hpj_disk_opportunity_study as s
 
 # Closed, checkpointed evidence archives only: never use immutable on live WALs.
 import sqlite3
 import tail_diagnostic_analysis as diagnostic
 from contextlib import closing
 def archive_access_metrics(case):
  assert not list(Path(case).glob('state.db-*'))
  with closing(sqlite3.connect((Path(case)/'state.db').resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as db:
   return ({(p,g):n for p,g,n in db.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')},dict(db.execute('SELECT name,value FROM metrics')))
 diagnostic.read_access_metrics=archive_access_metrics
 data=tmp/'data';shutil.copytree(root/'data/development',data)
 assert s.audit(data)['passed']
 case=data/'moving_shared-74801-r1/Full'
 def modify_json(name,callback):
  p=case/name;original=p.read_bytes();v=json.loads(original);callback(v);p.write_text(json.dumps(v));return p,original
 for field,callback in [('effective_mib_s',lambda v:v.__setitem__('effective_mib_s',v['effective_mib_s']*1.01)),('request_p99_s',lambda v:v.__setitem__('request_p99_s',v['request_p99_s']*.99))]:
  p,original=modify_json('result.json',callback);assert not s.audit(data)['passed'],field;p.write_bytes(original);tests.append(field)
 p,original=modify_json('execution.json',lambda v:v.__setitem__('binary_sha256','0'*64));assert not s.audit(data)['passed'];p.write_bytes(original);tests.append('binary receipt')
 p,original=modify_json('config.json',lambda v:v['policy'].__setitem__('measured_static_reuse_value',True));assert not s.audit(data)['passed'];p.write_bytes(original);tests.append('H switch')
 p,original=modify_json('requests.json',lambda v:v.pop());assert not s.audit(data)['passed'];p.write_bytes(original);tests.append('missing request')
 metric='request_cost_remote_samples'
 p,original=modify_json('result.json',lambda v:v['metrics'].__setitem__(metric,v['metrics'][metric]+1))
 db=sqlite3.connect(case/'state.db');db.execute('UPDATE metrics SET value=value+1 WHERE name=?',(metric,));db.commit();db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchall();db.execute('PRAGMA journal_mode=DELETE').fetchone();db.close()

 for sidecar in case.glob('state.db-*'):
  if sidecar.name.endswith('-wal'):assert sidecar.stat().st_size==0
  sidecar.unlink()
 assert not s.audit(data)['passed']
 p.write_bytes(original);db=sqlite3.connect(case/'state.db');db.execute('UPDATE metrics SET value=value-1 WHERE name=?',(metric,));db.commit();db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchall();db.execute('PRAGMA journal_mode=DELETE').fetchone();db.close();tests.append('matching JSON/SQLite forged read count')

 for sidecar in case.glob('state.db-*'):
  if sidecar.name.endswith('-wal'):assert sidecar.stat().st_size==0
  sidecar.unlink()
 assert s.audit(data)['passed']
print(json.dumps(dict(passed=True,intact_accepted=True,restored_accepted=True,rejected=tests)))
