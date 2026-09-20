import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from affinity_joint_study import configuration,synthetic,VARIANTS

class AffinityJointTest(unittest.TestCase):
    def test_only_declared_factors_change(self):
        configs={n:configuration(n,Path('/case'),Path('/remote'),8,True) for n in VARIANTS}
        for a,b,keys in [('H','B',{'measured_shift_reset'}),('P','B',{'measured_affinity_gate'}),
                         ('I','H',{'measured_affinity_gate'}),('I','P',{'measured_shift_reset'}),
                         ('J','I',{'measured_joint_admission'}),('J','J-no-H',{'measured_shift_reset'}),
                         ('J','J-no-P',{'measured_affinity_gate'})]:
            self.assertEqual(configs[a]['gpus'],configs[b]['gpus'])
            self.assertEqual({k for k,v in configs[a]['policy'].items() if v!=configs[b]['policy'][k]},keys)
        for c in configs.values():
            self.assertTrue(c['policy']['private_cache_domains'])
            self.assertTrue(c['policy']['measured_track_affinity'])
    def test_affinity_shift_keeps_same_hot_keys(self):
        b=dict(scenario='caller_shift',seed=912,requests=1200,shard_mib=2)
        events=synthetic(b)
        self.assertEqual(events,synthetic(b))
        for phase in range(4):
            quarter=events[phase*300:(phase+1)*300]
            self.assertTrue(all(e['key']<4 or e['key']>=32 for e in quarter))
            self.assertGreater(sum(e['caller']==phase%3 for e in quarter),240)
    def test_hot_shift_keeps_callers_fixed(self):
        b=dict(scenario='hot_shift',seed=914,requests=384,shard_mib=2)
        events=synthetic(b)
        self.assertTrue(all(e['caller']==i%3 for i,e in enumerate(events)))
        self.assertEqual(sum(e['bytes'] for e in events),768*1024*1024)

if __name__=='__main__':unittest.main()
