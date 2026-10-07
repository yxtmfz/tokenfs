from pathlib import Path
import json,subprocess,tempfile
r=Path(__file__).resolve().parents[1]/'models';count=0
with tempfile.TemporaryDirectory() as t:
 t=Path(t)
 for group in ['calibration','confirmed','headroom','support']:
  gold=json.loads((r/group/'screen.json').read_text());names=list(gold['rows'][0]['variants']);bins={}
  for name in names:
   binary=t/(group+'-'+name);bins[name]=binary
   driver=r/group/('original-replay.cpp' if group=='confirmed' and name=='original' else 'replay.cpp')
   subprocess.run(['c++','-std=c++17','-O2','-I',str(r/group/name),str(driver),'-o',str(binary)],check=True)
  for row in gold['rows']:
   for name in names:
    result=subprocess.check_output([str(bins[name]),str(r/'inputs'/(row['input']+'.txt')),'prior'],text=True).splitlines()
    assert result==row['variants'][name],(group,name,row['input']);count+=len(result)
 test=t/'causal-test';subprocess.run(['c++','-std=c++17','-O2',str(r/'calibration/causal_test.cpp'),'-o',str(test)],check=True);subprocess.run([str(test)],check=True)
 # Selected native source must reproduce the chosen prototype exactly.
 d=r/'source-check';binary=t/'source-check';subprocess.run(['c++','-std=c++17','-O2','-I',str(d),str(d/'replay.cpp'),'-o',str(binary)],check=True)
 for row in json.loads((d/'replay-verification.json').read_text())['rows']:
  result=subprocess.check_output([str(binary),str(r/'inputs'/(row['input']+'.txt')),'prior'],text=True).splitlines()
  assert result==row['result'];count+=len(result)
 # The selected support-only formula must leave the NoHotspot model unchanged.
 for row in json.loads((r/'support/screen.json').read_text())['rows']:
  assert len({tuple(v[1].split()[:3]) for v in row['variants'].values()})==1
print(json.dumps(dict(passed=True,model_arms=count,selected_static_baseline_counts_preserved=True,actual_speed_evidence=False)))
