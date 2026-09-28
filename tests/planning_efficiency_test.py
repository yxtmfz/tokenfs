import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from acceptance_v2 import passes
import planning_efficiency_study as s
import component_ablation_study as old
class EfficiencyTest(unittest.TestCase):
 def test_exactly_same_inputs_and_isolated_flags(self):
  self.assertEqual(s.expected_spec(),old.expected_spec())
  self.assertEqual(sum(len(b['variants']) for b in s.expected_spec()['blocks']),12)
  for b in s.expected_spec()['blocks']:
   self.assertEqual(s.trace(b),old.trace(b));self.assertEqual(s.arm_order(b),old.arm_order(b))
  for name in s.VARIANTS:
   cfg=s.configuration(name,Path('/c'),Path('/r'),24,True)
   self.assertEqual(cfg['policy'].pop('efficient_measured_planning'),name!='PoolSIEVE1')
   self.assertEqual(cfg,old.configuration(name,Path('/c'),Path('/r'),24,True))
 def test_positive_is_not_five_percent_or_equality(self):
  x=dict(gain_pct=.0001,p99_change_pct=0,drain_gain_pct=0,mechanism_active=True,executed_actions_changed=True,baseline='CallerOnly')
  self.assertTrue(passes(x))
  for key,value in [('gain_pct',0),('gain_pct',-.01),('p99_change_pct',.0001),('drain_gain_pct',-.0001),('mechanism_active',False),('executed_actions_changed',False),('gain_pct',float('nan'))]:
   y=dict(x);y[key]=value;self.assertFalse(passes(y))
if __name__=='__main__':unittest.main()
