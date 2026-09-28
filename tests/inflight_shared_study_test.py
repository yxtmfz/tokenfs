import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import inflight_shared_study as s
class InflightStudyTest(unittest.TestCase):
 def test_fixed_matrix_and_fair_capability(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),12)
  self.assertEqual([b['seed'] for b in spec['blocks']],[3241,3261,3262])
  self.assertEqual(s.arm_order(spec['blocks'][0]),list(reversed(s.arm_order(spec['blocks'][1]))))
  a=s.configuration('InflightHP',Path('/c'),Path('/r'),24,True)
  b=s.configuration('AdaptiveHP',Path('/c'),Path('/r'),24,True)
  self.assertTrue(a['policy'].pop('coalesce_pending_reads'));self.assertFalse(b['policy'].pop('coalesce_pending_reads'));self.assertEqual(a,b)
  for name in ['PoolSIEVE1','PoolSIEVE2']:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertTrue(cfg['policy']['coalesce_pending_reads'])
   self.assertEqual(cfg['policy']['read_fill_buffer_bytes'],a['policy']['read_fill_buffer_bytes'])
   self.assertFalse(cfg['policy'].get('incremental_copy_cost',False))
  spec['blocks'][0]['seed']=0
  with self.assertRaises(ValueError):s.validate_spec(spec)
if __name__=='__main__':unittest.main()
