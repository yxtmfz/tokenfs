import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_reuse_study as s
import headroom_exploration_study as old
class RunReuseStudyTest(unittest.TestCase):
 def test_frozen_matrix_and_single_flag(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),18)
  self.assertEqual(len({tuple(s.arm_order(b)) for b in spec['blocks']}),6)
  for b in spec['blocks']:
   self.assertEqual(s.trace(b),old.trace(b))
   self.assertEqual(sorted(s.arm_order(b)),sorted(s.VARIANTS))
  for name in s.VARIANTS:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual(cfg['policy'].pop('persistent_run_reuse'),name=='Full')
   self.assertEqual(cfg,old.configuration('PoolSIEVE1' if name=='PoolSIEVE1' else 'Full',Path('/c'),Path('/r'),24,True))
if __name__=='__main__':unittest.main()
