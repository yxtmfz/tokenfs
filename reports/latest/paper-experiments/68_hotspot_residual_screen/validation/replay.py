"""Reproduce a local policy-mechanism screen. Outputs are not speed measurements."""
from pathlib import Path
import subprocess,tempfile,json,sys,hashlib
root=Path(__file__).resolve().parents[1]
if (root/'SHA256SUMS').exists():
 for line in (root/'SHA256SUMS').read_text().splitlines():
  h,p=line.split('  ',1);assert hashlib.sha256((root/p).read_bytes()).hexdigest()==h,p
results=[];tests=[]
with tempfile.TemporaryDirectory(prefix='tokenfs-residual-screen-') as tmp:
 for name in ['retained','residual','dispersion','recent']:
  exe=Path(tmp)/name;driver='replay-retained.cpp' if name=='retained' else 'replay-residual.cpp'
  subprocess.run(['c++','-std=c++17','-O2','-I',str(root/'source'/name),str(root/'validation'/driver),'-o',str(exe)],check=True)
  if name!='retained':
   test=Path(tmp)/(name+'-test')
   subprocess.run(['c++','-std=c++17','-O2','-I',str(root/'source'/name),str(root/'validation/disk-demand-test.cpp'),'-o',str(test)],check=True)
   test_result=subprocess.run([str(test)],check=True,text=True,capture_output=True)
   tests.append(dict(candidate=name,passed=True,output=test_result.stdout.strip()))
  for f in sorted((root/'inputs').glob('*.txt')):
   run=subprocess.run([str(exe),str(f),'prior'],text=True,capture_output=True,check=True)
   arms={}
   for line in run.stdout.splitlines():
    v,*fields=line.split();counts=dict((k,int(n)) for k,n in (x.split('=') for x in fields));arms[v]=counts
   results.append(dict(candidate=name,input=f.stem,arms=arms))
# A genuine H ablation: no prototype may secretly change NoHotspot decisions.
for row in results:
 reference=next(x for x in results if x['candidate']=='retained' and x['input']==row['input'])
 assert row['arms']['NoHotspot']==reference['arms']['NoHotspot']
answer=dict(passed=True,kind='deterministic_local_mechanism_screen',speed_evidence=False,server_runs=0,fixed_model_costs_us=dict(remote=21000,local=10500,copy=8000),requests_per_input=1152,tests=tests,results=results,limits='Instant completed-copy model, two-object ideal shared capture, three four-object disk domains. No FUSE, NVMe, SQLite, concurrency, runtime, CPU cost, throughput or p99 measurement. Inputs were already used for development; no holdout claim.')
if '--freeze-results' in sys.argv:
 (root/'screen.json').write_text(json.dumps(answer,indent=2)+'\n')
else:assert answer==json.loads((root/'screen.json').read_text())
print(json.dumps(dict(passed=True,policies=4,inputs=8,arm_replays=len(results)*4,prototype_tests=len(tests),no_hotspot_decisions_preserved=True,speed_evidence=False,server_runs=0)))
