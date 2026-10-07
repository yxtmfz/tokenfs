import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import integrated_hpj_guarded_study as original
import integrated_hpj_reverse_study as repeated
class ReverseOrderTest(unittest.TestCase):
 def test_all_inputs_and_capabilities_preserved(self):
  self.assertEqual(original.expected_spec(),repeated.expected_spec())
  for b in original.expected_spec()['blocks']:
   self.assertEqual(original.trace(b),repeated.trace(b))
   self.assertEqual(original.arm_order(b),list(reversed(repeated.arm_order(b))))
   for v in original.VARIANTS:
    args=(v,Path('/case'),Path('/remote'),24,True)
    self.assertEqual(original.configuration(*args),repeated.configuration(*args))
if __name__=='__main__':unittest.main()
