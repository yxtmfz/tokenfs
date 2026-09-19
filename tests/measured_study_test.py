import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from measured_study import application,configuration,synthetic,digest,VARIANTS

class MeasuredStudyTest(unittest.TestCase):
 def test_each_ablation_has_only_declared_policy_difference(self):
  root=Path('/test');base=configuration('AURA-adaptive',root,root/'remote',16,True)
  expected={'AURA-no-admission':{'measured_admission'},'AURA-no-aging':{'measured_aging'},'AURA-no-value':{'measured_value_victim'},'AURA-no-size':{'measured_size_aware'},'AURA-no-cost':{'measured_cost'},'AURA-synchronous':{'async_promote_on_read','async_cross_gpu_replica'},'AURA-no-joint':{'measured_admission','measured_value_victim'}}
  for name,keys in expected.items():
   cfg=configuration(name,root,root/'remote',16,True)
   self.assertEqual({k for k in base['policy'] if base['policy'][k]!=cfg['policy'][k]},keys)
   self.assertEqual(base['gpus'],cfg['gpus'])
 def test_real_trace_split_order_identity_and_arrivals(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'trace.jsonl';rows=[dict(timestamp=1000+i*100,hash_ids=[1,i+10],input_length=1024,output_length=20) for i in range(20)]
   p.write_text('\n'.join(json.dumps(r) for r in rows))
   _,dev,di=application(p,'development',0,6,1)
   _,held,hi=application(p,'confirmation',0,6,1,True)
   self.assertTrue({e['source_request'] for e in dev}.isdisjoint({e['source_request'] for e in held}))
   self.assertEqual([e['source_hash'] for e in held],['1','14','1','15','1','16'])
   self.assertEqual([e['release_s'] for e in held],[0,0,.1,.1,.2,.2])
   self.assertEqual(len({e['key'] for e in held}),4)
   self.assertEqual(di['sha256'],hi['sha256'])
 def test_mixed_fit_and_trace_seed_are_reproducible(self):
  for scene in ['stable','shift','scan','uniform','mixed_fit']:
   a=synthetic(scene,303,256,2);self.assertEqual(a,synthetic(scene,303,256,2))
   self.assertEqual(len(a[1]),256);self.assertLessEqual(max(a[0].values()),8)
   self.assertNotEqual(digest(a),digest(synthetic(scene,304,256,2)))

if __name__=='__main__':unittest.main()
