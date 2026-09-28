import unittest,sys,tempfile,sqlite3,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from evidence_benchmark import finalize_case_metrics
class FinalMetricsTest(unittest.TestCase):
 def test_shutdown_counters_without_changing_timing(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)
   with sqlite3.connect(p/'state.db') as db:
    db.execute('CREATE TABLE metrics(name TEXT,value INTEGER)')
    db.executemany('INSERT INTO metrics VALUES(?,?)',[('read_bytes',100),('shared_placement_no_gain',4)])
   r=dict(metrics={'read_bytes':100,'shared_placement_no_gain':3},job_wall_s=1.2,effective_mib_s=2.3)
   finalize_case_metrics(p,r,0)
   self.assertEqual(r['metrics']['shared_placement_no_gain'],4)
   self.assertEqual(r['job_wall_s'],1.2);self.assertEqual(r['effective_mib_s'],2.3)
   self.assertEqual(json.loads((p/'result.json').read_text()),r)
   with self.assertRaises(RuntimeError):finalize_case_metrics(p,r,1)
   with sqlite3.connect(p/'state.db') as db:db.execute("UPDATE metrics SET value=101 WHERE name='read_bytes'")
   with self.assertRaises(RuntimeError):finalize_case_metrics(p,r,0)
if __name__=='__main__':unittest.main()
