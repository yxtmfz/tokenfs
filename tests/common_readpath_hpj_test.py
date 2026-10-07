import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import common_readpath_hpj_study as study
class CommonReadpathStudyTest(unittest.TestCase):
 def test_frozen_single_component_controls(self):
  spec=study.expected_spec();study.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),24)
  for scene in ['moving_shared','public_toolagent']:
   b=[x for x in spec['blocks'] if x['scenario']==scene]
   self.assertEqual(study.arm_order(b[0]),study.arm_order(b[1])[::-1])
  c={n:study.configuration(n,Path('/case'),Path('/remote'),24,True) for n in study.VARIANTS}
  for arm,key in [('NoHotspot','measured_static_reuse_value'),('NoAffinity','shared_caller_only'),('NoJoint','measured_joint_admission'),('NoRAMFirst','ram_first_routing')]:
   self.assertEqual({k for k in c['Full']['policy'] if c['Full']['policy'][k]!=c[arm]['policy'][k]},{key})
  for arm,cfg in c.items():
   self.assertTrue(cfg['policy']['reuse_direct_read_tail'])
   self.assertEqual(cfg['policy']['ram_first_routing'],arm!='NoRAMFirst')
   self.assertEqual(sum(g['local_quota_mib'] for g in cfg['gpus']),24)
   self.assertEqual(cfg['policy']['read_fill_buffer_bytes'],4*1024*1024)
