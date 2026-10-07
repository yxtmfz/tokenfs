import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import read_tail_study as study
class ReadTailStudyTest(unittest.TestCase):
 def test_fixed_matrix_and_single_switch_controls(self):
  spec=study.expected_spec();study.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),16)
  for scene in ['moving_shared','public_toolagent']:
   blocks=[b for b in spec['blocks'] if b['scenario']==scene]
   self.assertEqual(study.arm_order(blocks[0]),study.arm_order(blocks[1])[::-1])
  configs={n:study.configuration(n,Path('/case'),Path('/remote'),24,True) for n in study.VARIANTS}
  def diff(a,b):
   return {k for k in configs[a]['policy'] if configs[a]['policy'][k]!=configs[b]['policy'][k]}
  self.assertEqual(diff('Full','NoTail'),{'reuse_direct_read_tail'})
  self.assertEqual(diff('NoHotspot','NoHotspotNoTail'),{'reuse_direct_read_tail'})
  self.assertEqual(diff('Full','NoHotspot'),{'measured_static_reuse_value'})
  self.assertTrue(all(not c['policy']['disk_opportunity_value'] for c in configs.values()))
