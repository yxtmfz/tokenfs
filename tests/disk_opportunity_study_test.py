import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import integrated_hpj_disk_opportunity_study as s

class DiskOpportunityStudyTest(unittest.TestCase):
 def test_matrix_and_reverse(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),24)
  self.assertEqual(len(spec['blocks']),4)
  for a,b in zip(spec['blocks'][:2],spec['blocks'][2:]):self.assertEqual(s.arm_order(a),s.arm_order(b)[::-1])
  bad=copy.deepcopy(spec);bad['blocks'][0]['seed']+=1
  with self.assertRaises(ValueError):s.validate_spec(bad)
 def test_controlled_ablations(self):
  full=s.configuration('Full',Path('/case'),Path('/remote'),24,True)
  for name,flag in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission')]:
   other=s.configuration(name,Path('/case'),Path('/remote'),24,True)
   self.assertEqual([k for k in full['policy'] if full['policy'][k]!=other['policy'][k]],[flag])
   expected=copy.deepcopy(full);expected['policy'][flag]=other['policy'][flag];self.assertEqual(expected,other)
  for name in s.VARIANTS:
   c=s.configuration(name,Path('/case'),Path('/remote'),24,True)
   self.assertFalse(c['policy']['profile_control_path']);self.assertFalse(c['policy'].get('request_trace_path'))
   self.assertEqual(sum(g['local_quota_mib'] for g in c['gpus']),24)
   self.assertEqual(c['policy']['disk_opportunity_value'],name not in ['OldFull','PoolSIEVE1'])

if __name__=='__main__':unittest.main()
