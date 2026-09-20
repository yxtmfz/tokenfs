import json
from pathlib import Path
import sys
import tempfile
import unittest
import subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from measured_study import application,configuration,synthetic,digest,VARIANTS

class MeasuredStudyTest(unittest.TestCase):
 def test_each_ablation_has_only_declared_policy_difference(self):
  root=Path('/test');base=configuration('AURA-adaptive',root,root/'remote',16,True)
  expected={'AURA-no-admission':{'measured_admission'},'AURA-no-aging':{'measured_aging'},'AURA-no-shift':{'measured_shift_reset'},'AURA-no-value':{'measured_value_victim'},'AURA-no-size':{'measured_size_aware'},'AURA-no-cost':{'measured_cost'},'AURA-synchronous':{'async_promote_on_read','async_cross_gpu_replica'},'AURA-no-joint':{'measured_admission','measured_value_victim'}}
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
 def test_domain_supplement_has_equal_caller_bytes_and_no_phase_oracle(self):
  from measured_domain_study import trace
  for scene in ['domain_stable','domain_shift']:
   block=dict(scenario=scene,seed=701,requests=384,shard_mib=2)
   events=trace(block)
   self.assertEqual(events,trace(block))
   for gpu in range(3):self.assertEqual(sum(e['bytes'] for e in events if e['caller']==gpu),256*1024*1024)
   self.assertTrue(all(set(e)=={'index','key','caller','bytes'} for e in events))
   self.assertNotEqual(events,trace(dict(block,seed=702)))
 def test_domain_validation_refuses_to_modify_existing_evidence(self):
  script=Path(__file__).resolve().parents[1]/'scripts/measured_multidomain_check.py'
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'sentinel.json').write_text('{"preserve":true}')
   result=subprocess.run([sys.executable,str(script),'--output',str(root),'--binary','unused','--reference','unused','--remote-root','unused'],capture_output=True,text=True)
   self.assertEqual(result.returncode,2)
   self.assertEqual([p.name for p in root.iterdir()],['sentinel.json'])
   self.assertEqual((root/'sentinel.json').read_text(),'{"preserve":true}')

class FreezeAuditTest(unittest.TestCase):
 def fixture(self, root):
  import hashlib
  sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  put=lambda p,x:p.write_text(json.dumps(x))
  src=root/'source.jsonl'
  src.write_text('\n'.join(json.dumps(dict(timestamp=i*100,hash_ids=[1,i+10],input_length=1024,output_length=20)) for i in range(20)))
  _,trace,_=application(src,'confirmation',0,6,1,True)
  spec=dict(blocks=[dict(id='heldout',scenario='mooncake_test',source_offset=0,requests=6,shard_mib=1,paced=True,variants=['AURA-adaptive'])])
  sp=root/'test-batch.json';put(sp,spec)
  hashes={k:'frozen-'+k for k in ['src/main.cpp','src/measured_policy.h','scripts/measured_study.py','scripts/evidence_benchmark.py','build-release/tokenfs']}
  freeze=dict(hashes=hashes,specifications={'test-batch':dict(sha256=sha(sp),canonical_sha256=digest(spec),runs=1)},public_windows=[dict(block='heldout',source=src.name,source_sha256=sha(src),trace_sha256=digest(trace))])
  fp=root/'freeze.json';put(fp,freeze)
  put(root/'measured-b3-confirmation-execution-context.json',dict(freeze_sha256=sha(fp),frozen_hashes=hashes))
  batch=root/'test-batch';case=batch/'heldout/AURA-adaptive';case.mkdir(parents=True)
  put(batch/'manifest.json',dict(spec=spec,binary_sha256=hashes['build-release/tokenfs'],source_hashes={k:v for k,v in hashes.items() if k!='build-release/tokenfs'},nvme_identity=dict(transport='tcp',address='traddr=28.10.10.13,trsvcid=4420',subsysnqn='nqn.2026-09.local.aura-kv:remote-cn7')))
  put(batch/'heldout/trace.json',trace)
  put(case/'result.json',dict(job_wall_s=7,completed_with_background_s=8))
  put(case/'requests.json',[dict(issued_s=i,completed_s=i+.5,seconds=.49,release_s=e['release_s']) for i,e in enumerate(trace)])
  script=Path(__file__).resolve().parents[1]/'scripts/measured_freeze_audit.py'
  return lambda:subprocess.run([sys.executable,str(script),'--evidence-root',str(root),'--trace-dir',str(root),'--freeze',str(fp)],capture_output=True,text=True)
 def test_accepts_consistent_freeze_and_rejects_public_source_change(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);run=self.fixture(root);ok=run()
   self.assertEqual(ok.returncode,0,ok.stderr)
   self.assertEqual(json.loads(ok.stdout)['checked_performance_cases'],1)
   src=root/'source.jsonl';src.write_text(src.read_text()+'\n')
   bad=run();self.assertNotEqual(bad.returncode,0)
   self.assertIn('changed public source',bad.stdout)
 def test_rejects_binary_identity_or_missing_source_record(self):
  for problem in ['binary','source']:
   with self.subTest(problem=problem),tempfile.TemporaryDirectory() as d:
    root=Path(d);run=self.fixture(root);p=root/'test-batch/manifest.json';m=json.loads(p.read_text())
    if problem=='binary':m['binary_sha256']='different-program'
    else:del m['source_hashes']['src/main.cpp']
    p.write_text(json.dumps(m));bad=run()
    self.assertNotEqual(bad.returncode,0)
    self.assertFalse(json.loads(bad.stdout)['passed'])
 def test_rejects_invalid_timeline_and_nan_completion(self):
  for problem in ['backward','latency','release','background']:
   with self.subTest(problem=problem),tempfile.TemporaryDirectory() as d:
    root=Path(d);run=self.fixture(root);case=root/'test-batch/heldout/AURA-adaptive'
    if problem=='background':
     p=case/'result.json';v=json.loads(p.read_text());v['completed_with_background_s']=float('nan')
    else:
     p=case/'requests.json';v=json.loads(p.read_text())
     if problem=='backward':v[1]['issued_s']=.1
     elif problem=='latency':v[1]['seconds']=4
     else:v[1]['release_s']=9
    p.write_text(json.dumps(v));bad=run()
    self.assertNotEqual(bad.returncode,0)
    self.assertFalse(json.loads(bad.stdout)['passed'])

if __name__=='__main__':unittest.main()
