import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import shared_cache_pilot as s
class SharedPilotTest(unittest.TestCase):
    def test_isolation(self):
        cfg=[s.configuration(n,Path('/case'),Path('/remote'),8,True) for n in s.VARIANTS]
        self.assertEqual({k for k in cfg[1]['policy'] if cfg[1]['policy'][k]!=cfg[2]['policy'][k]}, {'peer_cache_reads'})
        self.assertEqual({k for k in cfg[0]['policy'] if cfg[0]['policy'][k]!=cfg[1]['policy'][k]}, {'private_cache_domains'})
        for c in cfg:
            self.assertTrue(c['policy']['readonly_canonical'])
            self.assertTrue(c['policy']['measured_shift_reset'])
            self.assertTrue(c['policy']['measured_joint_admission'])
    def test_budget(self):
        for stage,n in [('development',18),('correctness',3)]:
            spec=json.loads((Path(__file__).resolve().parents[1]/f'study-configs/shared-cache-pilot-{stage}.json').read_text())
            s.validate_spec(spec)
            self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),n)
    def test_disjoint(self):
        events=s.trace(dict(seed=2701,scenario='disjoint',requests=384,shard_mib=2))
        domains=[{e['key'] for e in events if e['caller']==g} for g in range(3)]
        self.assertEqual([len(x) for x in domains],[4,4,4])
        self.assertFalse(domains[0]&domains[1] or domains[0]&domains[2] or domains[1]&domains[2])
if __name__=='__main__':unittest.main()
