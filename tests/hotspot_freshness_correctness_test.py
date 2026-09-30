import json,sys,tempfile,unittest,types
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import hotspot_freshness_correctness as d

class ContentDriverTest(unittest.TestCase):
 def test_receipts_follow_case_creation_and_record_both_binaries(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp).resolve();build=root/'build';build.mkdir()
   binary=build/'tokenfs';binary.write_bytes(b'candidate')
   reference=root/'old';reference.write_bytes(b'retained')
   (build/'CMakeCache.txt').write_text('CMAKE_BUILD_TYPE:STRING=Release')
   freeze=root/'freeze.json';freeze.write_text(json.dumps(dict(source_hashes={},binary_sha256=d.sha(binary))))
   events=[dict(key=1,caller=0,bytes=2*d.MIB,index=i) for i in range(96)]
   study=types.SimpleNamespace(SOURCES=[],VARIANTS=['Full','NoHotspot','OldFull'],trace=lambda _:events,configuration=lambda *args:dict(policy={'profile_control_path':False},gpus=[{'local_quota_mib':24}]))
   original_sha=d.sha;refhash='b09253aa1577e6104421b797641b8952bd151c988eb3d9bef562b82d210cde37';calls=[]
   def fake_run(selected,case,data,name,ev,expected,*args,**kwargs):
    self.assertFalse(case.exists())
    calls.append((name,selected));case.mkdir()
    (case/'requests.json').write_text(json.dumps([dict(x,sha256=expected['1']) for x in ev]))
    return dict(status='ok',verify_every_request=True,metrics={},retained_cache_bytes=[0])
   a=types.SimpleNamespace(study='fake',freeze=freeze,binary=binary,reference_binary=reference,remote_root=root/'remote',output=root/'out')
   with patch.object(d.importlib,'import_module',return_value=study),patch.object(d,'check_mount',return_value={}),patch.object(d,'run_case',side_effect=fake_run),patch.object(d.os,'fsync'),patch.object(d,'sha',side_effect=lambda p:refhash if p==reference else original_sha(p)):
    d.run(a)
   self.assertEqual(calls,[('Full',binary),('NoHotspot',binary),('OldFull',reference)])
   for v in study.VARIANTS:
    self.assertEqual(json.loads((a.output/v/'execution.json').read_text())['binary_sha256'],refhash if v=='OldFull' else original_sha(binary))
   self.assertEqual(json.loads((a.output/'audit.json').read_text())['requests'],288)

if __name__=='__main__':unittest.main()
