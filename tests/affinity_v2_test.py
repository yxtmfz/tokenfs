import unittest,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from affinity_v2_study import configuration,trace
class AffinityV2Test(unittest.TestCase):
    def test_exact_affinity_toggle(self):
        a=configuration('P-new',Path('/case'),Path('/remote'),8,True)
        b=configuration('P-off',Path('/case'),Path('/remote'),8,True)
        self.assertEqual(a['gpus'],b['gpus'])
        self.assertEqual({k for k in a['policy'] if a['policy'][k]!=b['policy'][k]},{'measured_affinity_gate'})
        self.assertTrue(a['policy']['measured_shift_reset']);self.assertTrue(a['policy']['measured_joint_admission'])
    def test_reentry_workload(self):
        b=dict(scenario='domain_return',seed=1701,requests=384,shard_mib=2)
        rows=trace(b);self.assertEqual(rows,trace(b));self.assertEqual(sum(e['bytes'] for e in rows),768*1048576)
        for i in range(4):self.assertEqual({e['caller'] for e in rows[i*96:(i+1)*96]},{i%3})
if __name__=='__main__':unittest.main()
