import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import burst_reuse_study as s
class BurstStudyTest(unittest.TestCase):
 def test_controlled_change(self):
  c={n:s.configuration(n,Path('/case'),Path('/remote'),24,True) for n in s.VARIANTS}
  self.assertEqual({k for k in c['OldHP']['policy'] if c['OldHP']['policy'][k]!=c['BurstHP']['policy'][k]},{'measured_burst_reuse'})
  self.assertEqual({k for k in c['PoolSIEVE1']['policy'] if c['PoolSIEVE1']['policy'][k]!=c['PoolSIEVE2']['policy'][k]},{'read_through_min_reads'})
  for cfg in c.values():
   self.assertEqual(sum(g['local_quota_mib'] for g in cfg['gpus']),24)
   self.assertTrue(cfg['policy']['lean_read_accounting'] and cfg['policy']['backend_direct_io'])
 def test_budget(self):
  for stage,n in [('development',18),('correctness',7)]:
   spec=s.expected_spec(stage);s.validate_spec(spec)
   self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),n)
   spec['blocks'][0]['seed']+=100
   with self.assertRaises(ValueError):s.validate_spec(spec)
 def test_trace_is_policy_blind(self):
  for b in s.expected_spec('development')['blocks']:
   events=s.trace(b);self.assertEqual(len(events),576)
   self.assertTrue(all(set(e)=={'index','key','caller','bytes'} for e in events))
   b2=dict(b,variants=[]);self.assertEqual(s.trace(b2),events)
if __name__=='__main__':unittest.main()
