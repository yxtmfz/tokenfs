import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrated_hpj_exactverify_study as s
import run_decay_study as previous
class IntegratedExactVerifyStudyTest(unittest.TestCase):
 def test_controlled_ablations_and_matrix(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),10)
  self.assertEqual(s.trace(spec['blocks'][0]),s.trace(spec['blocks'][1]))
  self.assertEqual(s.arm_order(spec['blocks'][0]),list(reversed(s.arm_order(spec['blocks'][1]))))
  for b in spec['blocks']:
   self.assertEqual(s.trace(b),previous.trace(b))
   self.assertEqual(sorted(s.arm_order(b)),sorted(s.VARIANTS))
  full=s.configuration('Full',Path('/c'),Path('/r'),24,True)
  for name,flag in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission')]:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual({k for k in cfg['policy'] if cfg['policy'][k]!=full['policy'][k]},{flag})
   self.assertEqual(cfg['gpus'],full['gpus'])
  for name in s.VARIANTS:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertTrue(cfg['policy']['coalesce_pending_reads'])
   self.assertFalse(cfg['policy']['profile_control_path'])
   self.assertNotIn('request_trace_path',cfg['policy'])
   self.assertTrue(cfg['policy']['batch_background_metrics'])
   self.assertTrue(cfg['policy']['batch_policy_events'])
   self.assertTrue(cfg['policy']['retain_read_fill'])
   self.assertTrue(cfg['policy']['capture_local_reads'])
   self.assertTrue(cfg['policy']['bounded_cost_warmup'])
   self.assertEqual(sum(g['local_quota_mib'] for g in cfg['gpus']),24)
if __name__=='__main__':unittest.main()
