set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-calibrated-20260929
python3 - <<'PY'
from pathlib import Path
import sys,json,random,os,shutil,tarfile
sys.path.insert(0,'scripts')
import integrated_hpj_cohort_calibrated_study as study
from evidence_benchmark import sha,run_case,dump,MIB
from measured_study import check_mount
from tail_diagnostic_analysis import analyze_case
root=Path('/home/wjxt/tokenfs-cohort-tail-diagnostic-20260929')
remote=Path('/srv/tokenfs/remote-cn7/cohort-tail-diagnostic-20260929')
binary=Path('build-release/tokenfs').resolve()
freeze=json.loads(Path('study-configs/integrated-hpj-cohort-calibrated-freeze.json').read_text())
assert sha(binary)==freeze['binary_sha256']=='0cf7eb8361a797063ad05212a9cd65fad77ad2ad09674c6f2c6e987a90431cd8'
assert freeze['source_hashes']=={p:sha(Path(p)) for p in study.SOURCES}
identity=check_mount(remote.parent,False)
root.mkdir(exist_ok=False);(remote/'gpu0').mkdir(parents=True,exist_ok=False)
b=study.expected_spec()['blocks'][0];events=study.trace(b);expected={}
for key in sorted({e['key'] for e in events}):
 p=remote/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(b['seed']*100000+key).randbytes(MIB)
 with p.open('wb') as f:f.write(payload*2);f.flush();os.fsync(f.fileno())
 expected[str(key)]=sha(p)
dump(root/'manifest.json',dict(diagnostic_only=True,speed_evidence=False,binary_sha256=sha(binary),source_hashes=freeze['source_hashes'],spec=b,variants=['Full','PoolSIEVE1'],remote_data=str(remote),**identity))
dump(root/'trace.json',events);dump(root/'objects.json',expected)
diagnoses=[]
for v in ['Full','PoolSIEVE1']:
 case=root/v;cfg=study.configuration(v,case,remote,24,True)
 cfg['policy']['request_trace_path']=str(case/'request-trace.json')
 run_case(binary,case,remote,v,events,expected,24,False,True,configuration=cfg)
 d=analyze_case(case);d['strategy']=v;diagnoses.append(d)
 print(json.dumps({k:d[k] for k in ['strategy','passed','requests','event_count','tail_means','copy_mean_ms','copy_verify_mean_ms']}),flush=True)
dump(root/'diagnosis.json',dict(diagnostic_only=True,speed_evidence=False,runs=diagnoses))
shutil.rmtree(remote)
assert not any(str(root) in line for line in Path('/proc/mounts').read_text().splitlines())
with tarfile.open('/home/wjxt/cohort-tail-diagnostic-evidence.tar.gz','w:gz') as t:
 for f in root.rglob('*'):
  if f.is_file() and f.suffix in ['.json','.db','.log'] and not any(x.startswith('cache') for x in f.relative_to(root).parts):t.add(f,arcname=str(f.relative_to(root)))
print('ARCHIVE_SHA256',sha(Path('/home/wjxt/cohort-tail-diagnostic-evidence.tar.gz')))
PY
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected remaining TokenFS process'; exit 2; fi
