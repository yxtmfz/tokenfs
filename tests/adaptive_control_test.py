import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import adaptive_control_study as s
class AdaptiveControlTest(unittest.TestCase):
 def test_fixed_budget(self):
  for stage,n in [('development',18),('correctness',6)]:
   spec=s.expected_spec(stage);s.validate_spec(spec)
   self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),n)
   for b in spec['blocks']:
    self.assertEqual(set(s.arm_order(b)),set(s.VARIANTS))
    self.assertEqual(len(s.trace(b)),b['requests'])
   spec['blocks'][0]['seed']+=100
   with self.assertRaises(ValueError):s.validate_spec(spec)
 def test_equal_budget_and_baselines(self):
  cs={n:s.configuration(n,Path('/case'),Path('/remote'),24,True) for n in s.VARIANTS}
  for c in cs.values():
   self.assertEqual(sum(g['local_quota_mib'] for g in c['gpus']),24)
   self.assertTrue(c['policy']['profile_control_path'] and c['policy']['lean_read_accounting'] and c['policy']['backend_direct_io'])
  x=cs['PoolSIEVE1']['policy'];y=cs['PoolSIEVE2']['policy']
  self.assertEqual({k for k in x if x[k]!=y[k]},{'read_through_min_reads'})
  self.assertTrue(cs['AdaptiveHP']['policy']['adaptive_reuse_control'])
  self.assertFalse(y['adaptive_reuse_control'])
 def test_balanced_order(self):
  for scene in ['uniform','moving_shared']:
   bs=[b for b in s.expected_spec('development')['blocks'] if b['scenario']==scene]
   for n in s.VARIANTS:self.assertEqual({s.arm_order(b).index(n) for b in bs},{0,1,2})
if __name__=='__main__':unittest.main()
