import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrated_hpj_cohort_caller_independent_study as s
import run_decay_study as previous
class IndependentHPJTest(unittest.TestCase):
 def test_controlled_ablations_and_matrix(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),34)
  self.assertEqual(len({b['seed'] for b in spec['blocks']}),8)
  for b in spec['blocks']:
   if b['scenario']=='moving_shared':self.assertEqual(s.trace(b),previous.trace(b))
   self.assertEqual(len(s.trace(b)),1152)
   self.assertEqual(sorted(s.arm_order(b)),sorted(b['variants']))
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
   self.assertEqual(cfg['policy']['cohort_reuse_prior'],name!='PoolSIEVE1')
   self.assertEqual(cfg['policy']['recent_value_floor'],name!='PoolSIEVE1')
   self.assertEqual(sum(g['local_quota_mib'] for g in cfg['gpus']),24)
 def test_frozen_spec_and_public_windows(self):
  import json,copy
  spec=s.expected_spec();bad=copy.deepcopy(spec);bad['blocks'][0]['seed']+=10
  with self.assertRaises(ValueError):s.validate_spec(bad)
  p=json.loads((Path(__file__).resolve().parents[1]/'study-configs/independent-hpj-public.json').read_text())
  used=set()
  for prior in p['prior_trace_files']:used.update(range(prior['min'],prior['max']+1))
  for w in p['windows']:
   ids=set(range(w['start'],w['end']+1));self.assertFalse(ids & used);used.update(ids)
   self.assertEqual(len(w['events']),1152)
   self.assertTrue(all(e['caller']==e['source_request']%3 for e in w['events']))
if __name__=='__main__':unittest.main()
