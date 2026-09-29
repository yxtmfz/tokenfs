import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import headroom_exploration_study as s
import burst_interval_study as old
class HeadroomStudyTest(unittest.TestCase):
 def test_six_fixed_runs_and_one_changed_flag(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),6)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3271,3291])
  for b in spec['blocks']:
   self.assertEqual(s.trace(b),old.trace(b))
   self.assertEqual(sorted(s.arm_order(b)),sorted(s.VARIANTS))
  for name in s.VARIANTS:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual(cfg['policy'].pop('reuse_scaled_exploration'),name=='Full')
   self.assertEqual(cfg,old.configuration('PoolSIEVE1' if name=='PoolSIEVE1' else 'Full',Path('/c'),Path('/r'),24,True))
if __name__=='__main__':unittest.main()
