set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-submit-20260929
python3 - <<'PY'
from pathlib import Path
import sys,json,random,os,shutil
sys.path.insert(0,'scripts')
import integrated_hpj_cohort_caller_submit_study as study
from evidence_benchmark import sha,run_case,dump,MIB
from measured_study import check_mount
root=Path('/home/wjxt/tokenfs-integrated-hpj-cohort-caller-submit-evidence/oldnew')
remote=Path('/srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-submit-20260929/oldnew')
versions={}
for name,tag in [('old','integrated-hpj-cohort-caller'),('new','integrated-hpj-cohort-caller-submit')]:
 repo=Path('/home/wjxt/projects/tokenfs-'+tag+'-20260929')
 freeze=json.loads((repo/'study-configs'/f'{tag}-freeze.json').read_text())
 binary=repo/'build-release/tokenfs'
 assert sha(binary)==freeze['binary_sha256']
 assert all(sha(repo/p)==h for p,h in freeze['source_hashes'].items())
 versions[name]=dict(tag=tag,binary=str(binary),freeze=freeze)
root.mkdir(exist_ok=False);(remote/'gpu0').mkdir(parents=True,exist_ok=False)
b=study.expected_spec()['blocks'][0];events=study.trace(b);expected={}
for key in sorted({e['key'] for e in events}):
 p=remote/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(b['seed']*100000+key).randbytes(MIB)
 with p.open('wb') as f:f.write(payload*2);f.flush();os.fsync(f.fileno())
 expected[str(key)]=sha(p)
order=['old','new','new','old']
dump(root/'manifest.json',dict(versions=versions,order=order,spec=b,remote_data=str(remote),output=str(root),**check_mount(remote,False)))
dump(root/'trace.json',events);dump(root/'objects.json',expected)
rows=[]
for i,name in enumerate(order):
 case=root/f'{i+1}-{name}';cfg=study.configuration('Full',case,remote,24,True)
 before=study.environment()
 r=run_case(Path(versions[name]['binary']),case,remote,'Full',events,expected,24,False,True,configuration=cfg)
 dump(case/'environment.json',dict(before=before,after=study.environment()))
 row=dict(index=i+1,version=name,mib_s=r['effective_mib_s'],p99_ms=r['request_p99_s']*1000)
 rows.append(row);print(json.dumps(row),flush=True)
dump(root/'summary.json',rows)
shutil.rmtree(remote)
PY
