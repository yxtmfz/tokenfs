import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import stationary_stability_study as s
import headroom_exploration_study as old
class StabilityTest(unittest.TestCase):
 def test_balanced_frozen_same_inputs_and_policy(self):
  spec=s.expected_spec();s.validate_spec(spec)
  self.assertEqual(sum(len(b['variants']) for b in spec['blocks']),18)
  for seed in [3271,3291]:
   bb=[b for b in spec['blocks'] if b['seed']==seed]
   self.assertEqual([b['repeat'] for b in bb],[1,2,3])
   for name in s.VARIANTS:self.assertEqual(sorted(s.arm_order(b).index(name) for b in bb),[0,1,2])
   self.assertTrue(all(s.trace(b)==old.trace(bb[0]) for b in bb))
  for name in s.VARIANTS:self.assertEqual(s.configuration(name,Path('/c'),Path('/r'),24,True),old.configuration(name,Path('/c'),Path('/r'),24,True))
  changed=copy.deepcopy(spec);changed['blocks'][0]['repeat']=2
  with self.assertRaises(ValueError):s.validate_spec(changed)
 def test_repeat_statistics_do_not_hide_a_loss(self):
  rows=[];pairs=[]
  for seed in [3271,3291]:
   for i in range(3):
    bid=f'stationary_shared-{seed}-r{i+1}'
    for name in s.VARIANTS:rows.append(dict(block=bid,strategy=name,mib_s=101 if name=='Full' else 100,p99_ms=10))
    for name in s.VARIANTS[1:]:pairs.append(dict(seed=seed,baseline=name,gain_pct=1,p99_change_pct=0,drain_gain_pct=1,executed_actions_changed=True))
  x=s.stability(rows,pairs)
  self.assertTrue(all(v['stability_screen'] for v in x));self.assertAlmostEqual(x[0]['paired_gain_geo_pct'],1)
  pairs[0]['gain_pct']=-.1
  x=s.stability(rows,pairs)[0]
  self.assertFalse(x['stability_screen']);self.assertEqual(x['speed_wins'],2);self.assertLess(x['paired_log_t95_pct'][0],0)
 def test_tail_loss_and_missing_repeat_fail(self):
  rows=[];pairs=[]
  for seed in [3271,3291]:
   for i in range(3):
    for name in s.VARIANTS:rows.append(dict(block=f'stationary_shared-{seed}-r{i+1}',strategy=name,mib_s=100+i,p99_ms=10))
    for name in s.VARIANTS[1:]:pairs.append(dict(seed=seed,baseline=name,gain_pct=2,p99_change_pct=.001 if i==0 else -1,drain_gain_pct=1,executed_actions_changed=False))
  self.assertTrue(all(not x['stability_screen'] for x in s.stability(rows,pairs)))
  with self.assertRaises(ValueError):s.stability(rows[:-1],pairs)
if __name__=='__main__':unittest.main()
