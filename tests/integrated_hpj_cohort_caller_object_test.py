import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrated_hpj_cohort_caller_object_study as s
class ObjectCohortTest(unittest.TestCase):
 def test_single_switch_ablations_and_reference(self):
  full=s.configuration('Full',Path('/c'),Path('/r'),24,True)
  self.assertEqual(full,s.configuration('OldFull',Path('/c'),Path('/r'),24,True))
  for name,flag in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission')]:
   c=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual({k for k in full['policy'] if full['policy'][k]!=c['policy'][k]},{flag})
   self.assertEqual(full['gpus'],c['gpus'])
 def test_reversed_identical_inputs(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),24)
  for a,b in zip(spec['blocks'][:2],spec['blocks'][2:]):
   self.assertEqual(s.trace(a),s.trace(b));self.assertEqual(len(s.trace(a)),1152)
   self.assertEqual(s.arm_order(a),s.arm_order(b)[::-1])
   self.assertEqual(set(s.arm_order(a)),set(s.VARIANTS))
  bad=copy.deepcopy(spec);bad['blocks'][0]['seed']+=1
  with self.assertRaises(ValueError):s.validate_spec(bad)
if __name__=='__main__':unittest.main()
