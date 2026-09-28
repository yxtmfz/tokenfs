import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import read_fill_study as s
class ReadFillStudyTest(unittest.TestCase):
 def test_fixed_twelve(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),12)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3231,3232])
  self.assertEqual(s.arm_order(spec['blocks'][0]),list(reversed(s.arm_order(spec['blocks'][1]))))
  spec['blocks'][0]['seed']=3233
  with self.assertRaises(ValueError):s.validate_spec(spec)
 def test_same_path_all_policies(self):
  for p in s.POLICIES:
   old=s.configuration(p+'-old',Path('/case'),Path('/remote'),24,True)
   new=s.configuration(p+'-fill',Path('/case'),Path('/remote'),24,True)
   self.assertEqual(new['policy'].pop('foreground_read_fill'),True)
   self.assertEqual(old['policy'].pop('foreground_read_fill'),False)
   self.assertEqual(old,new)
   self.assertEqual(sum(g['local_quota_mib'] for g in new['gpus']),24)
   self.assertEqual(new['policy']['read_fill_buffer_bytes'],4*s.MIB)
   self.assertFalse(new['policy']['profile_control_path'])
   self.assertNotIn('request_trace_path',new['policy'])
if __name__=='__main__':unittest.main()
