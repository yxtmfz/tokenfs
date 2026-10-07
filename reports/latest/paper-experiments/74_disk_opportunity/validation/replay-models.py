import json,subprocess,sys,tarfile,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve();models=root/'models';checked=0
with tempfile.TemporaryDirectory() as tmp:
 tmp=Path(tmp);source=tmp/'source';source.mkdir()
 with tarfile.open(root/'provenance/source.tar.gz') as t:t.extractall(source)
 groups=[('screen.json',['retained','deadline','residual','renewal_window'],'replay.cpp'),
         ('combined-screen.json',['recent_floor','competition_all','residual_floor','observed_repeat'],'replay.cpp'),
         ('deferred-screen.json',['retained'],'deferred.cpp'),
         ('deferred-combined-screen.json',['recent_floor','deadline'],'deferred.cpp'),
         ('source-equivalence.json',['source'],'source-replay.cpp')]
 for filename,variants,replay in groups:
  data=json.loads((models/filename).read_text())
  for variant in variants:
   include=source/'src' if variant=='source' else models/variant
   binary=tmp/(filename+'-'+variant)
   subprocess.run(['c++','-std=c++17','-O2','-I',str(include),str(models/replay),'-o',str(binary)],check=True)
   for row in data['rows']:
    output=subprocess.run([str(binary),str(models/'inputs'/(row['input']+'.txt')),'prior'],check=True,capture_output=True,text=True).stdout.splitlines()
    expected=row['variants'][variant] if 'variants' in row else row['results']
    assert output==expected,(filename,variant,row['input'],output,expected)
    checked+=len(output)
print(json.dumps(dict(passed=True,model_arms=checked,server_speed_claim=False)))
