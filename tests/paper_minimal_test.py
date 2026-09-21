from pathlib import Path
import sys,unittest,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from paper_minimal_study import configuration,VARIANTS
class MinimalStudyTest(unittest.TestCase):
 def test_isolation(self):
  cs={n:configuration(n,Path('/case'),Path('/remote'),8,True) for n in VARIANTS}
  for a,b,k in [('Full','no-H','measured_shift_reset'),('Full','no-J','measured_joint_admission'),('no-H','no-HJ','measured_joint_admission'),('no-J','no-HJ','measured_shift_reset')]:
   self.assertEqual({x for x,v in cs[a]['policy'].items() if v!=cs[b]['policy'][x]},{k})
   self.assertEqual(cs[a]['gpus'],cs[b]['gpus'])
  for c in cs.values():
   for k in ['measured_track_affinity','measured_affinity_gate','measured_affinity_recent_demand','measured_affinity_handover_epoch','affinity_placement']:self.assertFalse(c['policy'][k])
   self.assertTrue(c['policy']['backend_direct_io'])
 def test_sieve_admission_separate(self):
  a=configuration('SIEVE',Path('/case'),Path('/remote'),8,True)
  b=configuration('SIEVE-2hit',Path('/case'),Path('/remote'),8,True)
  self.assertEqual({k for k,v in a['policy'].items() if v!=b['policy'][k]},{'read_through_min_reads'})
  self.assertEqual(a['policy']['read_through_min_reads'],1)
  self.assertEqual(a['policy']['local_eviction_policy'],'sieve')
  self.assertNotIn('measured_policy',a['policy'])
 def test_fixed_sample_matrix(self):
  r=Path(__file__).resolve().parents[1];s=json.loads((r/'study-configs/paper-minimal-confirmation-01.json').read_text())
  self.assertEqual(sum(len(b['variants']) for b in s['blocks']),336)
  self.assertEqual(len(s['blocks']),48)
  self.assertEqual({b['seed'] for b in s['blocks']},set(range(2101,2113)))
  for b in s['blocks']:
   self.assertEqual(b['requests']*b['shard_mib'],768)
   self.assertEqual(b['quota_mib'],8)
