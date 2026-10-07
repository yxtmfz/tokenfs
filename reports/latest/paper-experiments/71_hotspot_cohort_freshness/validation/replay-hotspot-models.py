from pathlib import Path
import json,subprocess,tempfile
r=Path(__file__).resolve().parents[1]/'models';count=0
with tempfile.TemporaryDirectory() as t:
 t=Path(t)
 for group in ['renewal','blend','freshness']:
  gold=json.loads((r/group/'screen.json').read_text())
  names=list(gold['rows'][0]['variants']) if group!='freshness' else ['candidate']
  bins={}
  for name in names:
   binary=t/(group+'-'+name);bins[name]=binary
   subprocess.run(['c++','-std=c++17','-O2','-I',str(r/group/name),str(r/group/'replay.cpp'),'-o',str(binary)],check=True)
  for row in gold['rows']:
   for name in names:
    result=subprocess.check_output([str(bins[name]),str(r/'inputs'/(row['input']+'.txt')),'prior'],text=True).splitlines()
    expected=row['result'] if group=='freshness' else row['variants'][name]
    assert result==expected,(group,name,row['input']);count+=len(result)
 # Static-frequency baseline actions must not be weakened by any candidate.
 baseline={x['input']:x['variants']['retained'][1].split()[:3] for x in json.loads((r/'renewal/screen.json').read_text())['rows']}
 for group in ['renewal','blend','freshness']:
  for row in json.loads((r/group/'screen.json').read_text())['rows']:
   variants=[row['result']] if group=='freshness' else row['variants'].values()
   for values in variants:assert values[1].split()[:3]==baseline[row['input']]
print(json.dumps(dict(passed=True,model_arms=count,static_baseline_counts_preserved=True,actual_speed_evidence=False)))
