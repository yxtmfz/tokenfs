import unittest,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from affinity_v3_study import configuration,trace
class AffinityV3Test(unittest.TestCase):
    def test_numeric_reproduction_allowance(self):
        from affinity_v3_evidence import derived_matches
        self.assertTrue(derived_matches('ci95',[.95,1.01],[.95,1.0100000000000002]))
        self.assertFalse(derived_matches('ci95',[.95,1.01],[.95,1.01001]))
        self.assertFalse(derived_matches('p_holm',.01,.0100000000000002))
        self.assertFalse(derived_matches('ci95',[.95,1.01],[.95,float('nan')]))
    def test_exact_affinity_toggle(self):
        a=configuration('P-new',Path('/case'),Path('/remote'),8,True)
        b=configuration('P-off',Path('/case'),Path('/remote'),8,True)
        self.assertEqual(a['gpus'],b['gpus'])
        self.assertEqual({k for k in a['policy'] if a['policy'][k]!=b['policy'][k]},{'measured_affinity_gate'})
        self.assertTrue(a['policy']['measured_affinity_handover_epoch']);self.assertTrue(a['policy']['measured_shift_reset']);self.assertTrue(a['policy']['measured_joint_admission'])
    def test_reentry_workload(self):
        b=dict(scenario='domain_return',seed=1701,requests=384,shard_mib=2)
        rows=trace(b);self.assertEqual(rows,trace(b));self.assertEqual(sum(e['bytes'] for e in rows),768*1048576)
        for i in range(4):self.assertEqual({e['caller'] for e in rows[i*96:(i+1)*96]},{i%3})
    def test_handover_keeps_objects_within_task_pair(self):
        b=dict(scenario='affinity_handover',seed=1701,requests=384,shard_mib=2)
        rows=trace(b);self.assertEqual(rows,trace(b))
        for phase in range(8):
            group=(phase//2)%3;part=rows[phase*48:(phase+1)*48]
            self.assertEqual({e['caller'] for e in part},{(phase//2+phase%2)%3})
            self.assertTrue(all(group*4<=e['key']<group*4+4 or e['key']>=32 for e in part))
if __name__=='__main__':unittest.main()
