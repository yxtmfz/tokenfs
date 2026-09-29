set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then exit 2; fi
cd /home/wjxt/projects/tokenfs-burst-interval-20260929
python3 - <<'PY'
import sys,json,random,os,shutil,tarfile
from pathlib import Path
sys.path.insert(0,'scripts')
import burst_interval_study as s
from evidence_benchmark import run_case,dump,sha,MIB
from tail_diagnostic_analysis import analyze_case
root=Path('/home/wjxt/tokenfs-stationary-diagnostic-20260929');root.mkdir(exist_ok=False)
remote=Path('/srv/tokenfs/remote-cn7/stationary-diagnostic-20260929');(remote/'gpu0').mkdir(parents=True,exist_ok=False)
b=s.expected_spec()['blocks'][0];events=s.trace(b);expected={}
for key in sorted({e['key'] for e in events}):
 p=remote/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(b['seed']*100000+key).randbytes(MIB)
 with p.open('wb') as f:
  f.write(payload*b['shard_mib']);f.flush();os.fsync(f.fileno())
 expected[str(key)]=sha(p)
dump(root/'manifest.json',dict(diagnostic_only=True,spec=b,order=['Full','PoolSIEVE1'],binary_sha256=sha(Path('build-release/tokenfs')),freeze=json.loads(Path('study-configs/burst-interval-freeze.json').read_text()),trace=events,objects=expected))
summary=[]
for name in ['Full','PoolSIEVE1']:
 case=root/name;cfg=s.configuration(name,case,remote,24,True)
 cfg['policy'].update(request_trace_path=str(case/'request-trace.json'),profile_control_path=True)
 r=run_case(Path('build-release/tokenfs').resolve(),case,remote,name,events,expected,24,False,True,configuration=cfg)
 a=analyze_case(case);dump(case/'diagnosis.json',a)
 summary.append(dict(strategy=name,**{k:v for k,v in a.items() if k not in ['request_details','tail_requests']}))
 print(json.dumps(summary[-1]),flush=True)
dump(root/'summary.json',summary)
shutil.rmtree(remote)
with tarfile.open('/home/wjxt/stationary-diagnostic-evidence.tar.gz','w:gz') as t:
 for f in root.rglob('*'):
  if f.is_file() and f.suffix in ['.json','.db','.log']:t.add(f,arcname=str(f.relative_to(root)))
PY
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then exit 2; fi
sha256sum /home/wjxt/stationary-diagnostic-evidence.tar.gz
