import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import component_ablation_study as s

class ComponentAblationTest(unittest.TestCase):
 def test_single_factor_configs_and_common_capability(self):
  cfg={n:s.configuration(n,Path('/case'),Path('/remote'),24,True) for n in s.VARIANTS}
  full=cfg['Full']
  for n,flag in [('CallerOnly','shared_caller_only'),('Independent','measured_joint_admission')]:
   other=copy.deepcopy(cfg[n]);other['policy'][flag]=full['policy'][flag]
   self.assertEqual(other,full)
  for c in cfg.values():
   p=c['policy']
   self.assertTrue(p['coalesce_pending_reads'] and p['foreground_read_fill'] and p['request_read_costs'])
   self.assertEqual(p['read_fill_buffer_bytes'],4*s.MIB)
   self.assertEqual(sum(g['local_quota_mib'] for g in c['gpus']),24)
   self.assertFalse(p.get('incremental_copy_cost',False))
   self.assertFalse(p['profile_control_path'])
  for n in ['Full','CallerOnly','Independent']:
   self.assertTrue(all(cfg[n]['policy'][k] for k in ['adaptive_reuse_control','measured_shift_reset','measured_burst_reuse','shared_value_placement']))

 def test_fixed_budget_and_reject_seed_substitution(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),12)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3271,3272,3273])
  for b in spec['blocks']:
   self.assertEqual(set(s.arm_order(b)),set(s.VARIANTS))
   self.assertEqual(sum(e['bytes'] for e in s.trace(b)),1152*s.MIB)
  spec['blocks'][0]['seed']=3261
  with self.assertRaises(ValueError):s.validate_spec(spec)

 def test_stationary_and_moving_semantics(self):
  stable,moving,uniform=s.expected_spec()['blocks']
  for b in [stable,moving]:
   events=s.trace(b);self.assertEqual(events,s.trace(b))
   self.assertEqual(len(events),576)
   for i in range(0,576,4):self.assertEqual(len({e['key'] for e in events[i:i+4]}),1)
   for i,e in enumerate(events):
    phase=min(2,i*3//576)
    self.assertTrue(e['key']>=64 or (0<=e['key']<8 if b==stable else phase*8<=e['key']<phase*8+8))
  self.assertEqual({e['caller'] for e in s.trace(uniform)},{0,1,2})
  self.assertTrue(all(0<=e['key']<24 for e in s.trace(uniform)))

 def test_prepare_has_no_results_and_never_overwrites(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'plan';s.prepare(p)
   m=json.loads((p/'preflight.json').read_text())
   self.assertEqual(m['status'],'prepared_not_executed');self.assertFalse(m['binary_frozen'])
   self.assertEqual(len(list(p.glob('*/*/config.json'))),12)
   self.assertFalse(list(p.rglob('result.json')))
   with self.assertRaises(FileExistsError):s.prepare(p)

 def test_mechanism_requires_real_placement_and_displacement(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);events=[dict(action='SHARED_PLACE',logical_path='/k',gpu_id=1,reason='caller=0;victim_loss=1'),dict(action='ADMIT',logical_path='/k',gpu_id=1,reason='net_gain;displaced=2;uncertainty=0'),dict(action='REPLICATE_READY',logical_path='/k',gpu_id=1,reason='replica')]
   (p/'policy-events.json').write_text(json.dumps(events));a=s.mechanism(p)
   self.assertEqual((a['relocated'],a['admissions_with_displacement']),(1,1))
   events[0]['gpu_id']=0;events[1]['reason']='free_headroom_exploration;displaced=0;uncertainty=0';events.pop()
   (p/'policy-events.json').write_text(json.dumps(events));b=s.mechanism(p)
   self.assertEqual((b['relocated'],b['admissions_with_displacement']),(0,0))
   self.assertNotEqual(a['action_sha256'],b['action_sha256'])

if __name__=='__main__':unittest.main()
