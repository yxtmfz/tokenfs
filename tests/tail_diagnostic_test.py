import unittest,sys,sqlite3,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tail_diagnostic_study as s
from tail_diagnostic_analysis import intersection_ns,read_access_metrics

class TailDiagnosticTest(unittest.TestCase):
 def test_six_fixed_runs(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3221,3222])
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),6)
  spec['blocks'][0]['requests']=577
  with self.assertRaises(ValueError):s.validate_spec(spec)
 def test_only_telemetry_added(self):
  for arm in s.VARIANTS:
   c=s.configuration(arm,Path('/case'),Path('/remote'),24,True)
   self.assertEqual(c['policy'].pop('request_trace_path'),'/case/request-trace.json')
   self.assertEqual(c,s.previous.configuration(arm,Path('/case'),Path('/remote'),24,True))
 def test_committed_wal_visible(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);db=sqlite3.connect(root/'state.db')
   try:
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE gpu_access(logical_path TEXT,gpu_id INTEGER,read_count INTEGER)')
    db.execute('CREATE TABLE metrics(name TEXT,value INTEGER)');db.commit()
    db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    db.execute("INSERT INTO gpu_access VALUES('/gpu0/k',1,7)")
    db.execute("INSERT INTO metrics VALUES('read_open_count',7)");db.commit()
    self.assertTrue((root/'state.db-wal').stat().st_size>0)
    accesses,metrics=read_access_metrics(root)
    self.assertEqual(accesses,{('/gpu0/k',1):7});self.assertEqual(metrics,{'read_open_count':7})
   finally:db.close()
 def test_interval_union_no_double_count(self):
  self.assertEqual(intersection_ns(10,20,[(0,12),(11,15),(17,30)]),8)
  self.assertEqual(intersection_ns(10,20,[(0,5),(21,30)]),0)
if __name__=='__main__':unittest.main()
