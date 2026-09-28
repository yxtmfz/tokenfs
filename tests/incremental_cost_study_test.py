import unittest,sys,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import incremental_cost_study as s
class IncrementalCostStudyTest(unittest.TestCase):
 def test_matrix_and_single_variable(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),12)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3251,3252,3253])
  self.assertEqual(s.arm_order(spec['blocks'][0]),list(reversed(s.arm_order(spec['blocks'][1]))))
  cfg=s.configuration('IncrementalHP',Path('/c'),Path('/r'),24,True)
  old=s.configuration('AdaptiveHP',Path('/c'),Path('/r'),24,True)
  self.assertTrue(cfg['policy'].pop('incremental_copy_cost'))
  self.assertFalse(old['policy'].pop('incremental_copy_cost'))
  self.assertEqual(cfg,old)
  for b in spec['blocks']:
   self.assertEqual(len(s.trace(b)),576)
   self.assertEqual(s.trace(b),s.previous.trace(b))
  spec['blocks'][2]['seed']=3254
  with self.assertRaises(ValueError):s.validate_spec(spec)
if __name__=='__main__':unittest.main()
