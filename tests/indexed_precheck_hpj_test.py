import unittest,sys,json,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import indexed_precheck_hpj_study as study
class IndexedPrecheckStudyTest(unittest.TestCase):
 def test_implementation_gain_need_not_change_cache_actions(self):
  self.assertTrue(study.comparison_pass('NoIndexedPrecheck',1,-1,1,True,False))
  self.assertFalse(study.comparison_pass('NoHotspot',1,-1,1,True,False))
  self.assertFalse(study.comparison_pass('NoIndexedPrecheck',1,-1,-1,True,False))
  self.assertFalse(study.comparison_pass('NoIndexedPrecheck',1,0,1,True,False))
 def test_frozen_single_component_controls(self):
  spec=study.expected_spec();study.validate_spec(spec)
  self.assertEqual(json.loads((Path(__file__).resolve().parents[1]/'study-configs/indexed-precheck-development.json').read_text()),spec)
  self.assertEqual(spec['cpu_affinity'],[0,2,4,6])
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),24)
  for scene in ['moving_shared','public_toolagent']:
   b=[x for x in spec['blocks'] if x['scenario']==scene]
   self.assertEqual(study.arm_order(b[0]),study.arm_order(b[1])[::-1])
   shuffled=study.VARIANTS.copy();random.Random(1050000+b[0]['seed']).shuffle(shuffled)
   self.assertEqual(study.arm_order(b[0]),shuffled)
  c={n:study.configuration(n,Path('/case'),Path('/remote'),24,True) for n in study.VARIANTS}
  for arm,key in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission'),('NoIndexedPrecheck','indexed_shared_precheck')]:
   self.assertEqual({k for k in c['Full']['policy'] if c['Full']['policy'][k]!=c[arm]['policy'][k]},{key})
  for arm,cfg in c.items():
   self.assertTrue(cfg['policy']['reuse_direct_read_tail'])
   self.assertTrue(cfg['policy']['ram_first_routing'])
   self.assertTrue(cfg['policy']['object_weighted_cohort_prior'])
   self.assertTrue(cfg['policy']['precheck_shared_submission'])
   self.assertEqual(cfg['policy']['indexed_shared_precheck'],arm!='NoIndexedPrecheck')
   self.assertTrue(cfg['policy']['defer_background_submission_metrics'])
   self.assertTrue(cfg['policy']['batch_background_metrics'])
   self.assertEqual(sum(g['local_quota_mib'] for g in cfg['gpus']),24)
   self.assertEqual(cfg['policy']['read_fill_buffer_bytes'],4*1024*1024)
 def test_index_activation_and_short_content_are_distinct(self):
  for name in study.VARIANTS:
   with self.subTest(arm=name):
    cfg=study.configuration(name,Path('/case'),Path('/remote'),24,True)
    enabled=name!='PoolSIEVE1';indexed=name not in ['PoolSIEVE1','NoIndexedPrecheck']
    metrics=dict(submission_precheck_enabled=int(enabled),submission_precheck_index_enabled=int(indexed),
                 submission_precheck_attempts=2 if enabled else 0,submission_precheck_rejected=1 if enabled else 0)
    self.assertTrue(study.precheck_metrics_valid(metrics,cfg))
    self.assertFalse(study.precheck_metrics_valid(dict(metrics,submission_precheck_index_enabled=1-int(indexed)),cfg))
    self.assertFalse(study.precheck_metrics_valid(dict(metrics,submission_precheck_index_fallback=1),cfg))
    prefix=dict(metrics,submission_precheck_attempts=0,submission_precheck_rejected=0)
    self.assertTrue(study.precheck_metrics_valid(prefix,cfg,verify_content=True))
    self.assertEqual(study.precheck_metrics_valid(prefix,cfg),not enabled)
    self.assertFalse(study.precheck_metrics_valid(dict(metrics,submission_precheck_attempts=0,submission_precheck_rejected=1),cfg,True))
    if enabled:self.assertFalse(study.precheck_metrics_valid(dict(prefix,submission_precheck_enabled=0),cfg,True))
