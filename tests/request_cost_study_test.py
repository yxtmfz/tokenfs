import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import request_cost_study as s
class RequestCostStudyTest(unittest.TestCase):
 def test_fixed_six_and_common_path(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),6)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3241,3242])
  self.assertEqual(s.arm_order(spec['blocks'][0]),list(reversed(s.arm_order(spec['blocks'][1]))))
  for name in s.VARIANTS:
   cfg=s.configuration(name,Path('/case'),Path('/remote'),24,True)
   self.assertTrue(cfg['policy'].pop('request_read_costs'))
   self.assertEqual(cfg,s.previous.configuration(name+'-fill',Path('/case'),Path('/remote'),24,True))
  spec['blocks'][0]['requests']=577
  with self.assertRaises(ValueError):s.validate_spec(spec)
if __name__=='__main__':unittest.main()
