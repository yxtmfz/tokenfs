import unittest,sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import compact_planning_study as s
class JointPilotTest(unittest.TestCase):
 def test_factorial(self):
  configs={n:s.configuration(n,Path('/case'),Path('/remote'),24,True) for n in s.VARIANTS}
  for x,y,key in [('Shared','H','measured_shift_reset'),('Shared','P','shared_value_placement'),('H','HP','shared_value_placement'),('P','HP','measured_shift_reset'),('HP','Independent','measured_joint_admission')]:
   self.assertEqual({k for k in configs[x]['policy'] if configs[x]['policy'][k]!=configs[y]['policy'][k]},{key})
  for c in configs.values():self.assertEqual(sum(g['local_quota_mib'] for g in c['gpus']),24)
  self.assertEqual([g['local_quota_mib'] for g in configs['PoolSIEVE2']['gpus']],[24,0,0])
 def test_budget(self):
  for stage,n in [('development',18),('correctness',6)]:
   spec=json.loads((Path(__file__).resolve().parents[1]/f'study-configs/compact-planning-closeout-{stage}.json').read_text());s.validate_spec(spec)
   self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),n)
   spec['blocks'].append(spec['blocks'][0])
   with self.assertRaises(ValueError):s.validate_spec(spec)
 def test_only_observable_inputs(self):
  trace=s.trace(dict(seed=3001,requests=576,shard_mib=2))
  self.assertEqual(len(trace),576)
  self.assertTrue(all(set(e)=={'index','key','caller','bytes'} for e in trace))
  self.assertTrue(all(len({e['key'] for e in trace[i:i+4]})==1 for i in range(0,576,4)))
if __name__=='__main__':unittest.main()
