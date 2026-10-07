import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import submission_fence_hpj_study as study
class SubmissionFenceStudyTest(unittest.TestCase):
 def test_implementation_gain_need_not_change_cache_actions(self):
  self.assertTrue(study.comparison_pass('SyncSubmission',1,-1,1,True,False))
  self.assertFalse(study.comparison_pass('NoHotspot',1,-1,1,True,False))
  self.assertFalse(study.comparison_pass('SyncSubmission',1,-1,-1,True,False))
  self.assertFalse(study.comparison_pass('SyncSubmission',1,0,1,True,False))
 def test_frozen_single_component_controls(self):
  spec=study.expected_spec();study.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),24)
  for scene in ['moving_shared','public_toolagent']:
   b=[x for x in spec['blocks'] if x['scenario']==scene]
   self.assertEqual(study.arm_order(b[0]),study.arm_order(b[1])[::-1])
  c={n:study.configuration(n,Path('/case'),Path('/remote'),24,True) for n in study.VARIANTS}
  for arm,key in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission'),('SyncSubmission','defer_background_submission_metrics')]:
   self.assertEqual({k for k in c['Full']['policy'] if c['Full']['policy'][k]!=c[arm]['policy'][k]},{key})
  for arm,cfg in c.items():
   self.assertTrue(cfg['policy']['reuse_direct_read_tail'])
   self.assertTrue(cfg['policy']['ram_first_routing'])
   self.assertTrue(cfg['policy']['object_weighted_cohort_prior'])
   self.assertEqual(cfg['policy']['defer_background_submission_metrics'],arm!='SyncSubmission')
   self.assertTrue(cfg['policy']['batch_background_metrics'])
   self.assertEqual(sum(g['local_quota_mib'] for g in cfg['gpus']),24)
   self.assertEqual(cfg['policy']['read_fill_buffer_bytes'],4*1024*1024)
