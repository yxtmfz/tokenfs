import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrated_hpj_cohort_caller_lazy_study as s
class LazyPlanningTest(unittest.TestCase):
 def test_single_switch_ablations_and_reference(self):
  full=s.configuration('Full',Path('/c'),Path('/r'),24,True)
  self.assertEqual(full,s.configuration('OldFull',Path('/c'),Path('/r'),24,True))
  for name,flag in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission')]:
   c=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual({k for k in full['policy'] if full['policy'][k]!=c['policy'][k]},{flag})
   self.assertEqual(full['gpus'],c['gpus'])
 def test_frozen_twelve_case_screen(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),12)
  for b in spec['blocks']:
   self.assertEqual(len(s.trace(b)),1152)
   self.assertEqual(set(s.arm_order(b)),set(s.VARIANTS))
  bad=copy.deepcopy(spec);bad['blocks'][0]['seed']+=1
  with self.assertRaises(ValueError):s.validate_spec(bad)
if __name__=='__main__':unittest.main()
