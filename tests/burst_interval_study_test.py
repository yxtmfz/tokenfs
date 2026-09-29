import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import burst_interval_study as s
import planning_efficiency_study as old
class BurstIntervalStudyTest(unittest.TestCase):
 def test_frozen_matrix_and_only_one_policy_delta(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),12)
  self.assertEqual(len({b['seed'] for b in spec['blocks']}),4)
  for b in spec['blocks']:
   self.assertEqual(s.trace(b),old.trace(b))
   self.assertEqual(sorted(s.arm_order(b)),sorted(s.VARIANTS))
  for name in s.VARIANTS:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual(cfg['policy'].pop('burst_interval_survival'),name=='Full')
   self.assertEqual(cfg,old.configuration('PoolSIEVE1' if name=='PoolSIEVE1' else 'Full',Path('/c'),Path('/r'),24,True))
if __name__=='__main__':unittest.main()
