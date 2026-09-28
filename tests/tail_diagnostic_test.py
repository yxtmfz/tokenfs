import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import tail_diagnostic_study as s
from tail_diagnostic_analysis import intersection_ns

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
 def test_interval_union_no_double_count(self):
  self.assertEqual(intersection_ns(10,20,[(0,12),(11,15),(17,30)]),8)
  self.assertEqual(intersection_ns(10,20,[(0,5),(21,30)]),0)
if __name__=='__main__':unittest.main()
