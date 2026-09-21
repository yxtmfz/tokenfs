set -eu
case "$(hostname)" in
 cn7) . /home/wjxt/aura-kv-tools/env.sh;;
 cn8) . /home/wjxt/tokenfs-eval-tools-20260919/env.sh;;
 *) exit 2;;
esac
cd /home/wjxt/projects/tokenfs-paper-minimal-20260921
python3 - <<'PY'
from pathlib import Path
import json,hashlib,tarfile,subprocess,platform,sys
sys.path.insert(0,'scripts');import paper_minimal_study as study;study.activate()
host=platform.node();base=Path('/home/wjxt/tokenfs-paper-minimal-evidence')
names=['paper-minimal-correctness-01']+(['paper-minimal-development-01','paper-minimal-confirmation-01','paper-minimal-sensitivity-01'] if host=='cn7' else [])
for name in names:
 assert (base/(name+'.exit')).read_text().strip()=='0'
 a=study.core.audit(base/name);assert a['passed'] and a['checked_runs']==a['expected_runs']
mounts=[line for line in Path('/proc/mounts').read_text().splitlines() if str(base) in line];assert not mounts
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def cmd(argv):
 r=subprocess.run(argv,capture_output=True,text=True);return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
record=dict(host=host,binary_sha256=sha('build-release/tokenfs'),source_hashes={p:sha(p) for p in study.SOURCES},remaining_mounts=mounts,local=cmd(['findmnt','-J','--target',str(base)]),kernel=platform.release())
if host=='cn7':
 record['remote']=cmd(['findmnt','-J','--target','/srv/tokenfs/remote-cn7'])
 record['hardware']=dict(cpu=cmd(['lscpu','-J']),memory_kib=int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemTotal:'))),storage=cmd(['lsblk','-J','-o','NAME,SIZE,MODEL,LOG-SEC,PHY-SEC,FSTYPE,MOUNTPOINTS']),compiler=cmd(['c++','--version']))

(base/'final-context.json').write_text(json.dumps(record,indent=2)+'\n')
files=[p for p in base.rglob('*') if p.is_file() and not p.is_symlink() and p.suffix in ['.json','.log','.exit','.md']]
archive=Path('/home/wjxt')/('tokenfs-paper-minimal-'+host+'.tar.gz')
with tarfile.open(archive,'w:gz',compresslevel=1) as t:
 for p in sorted(files):t.add(p,arcname=host+'/'+str(p.relative_to(base)),recursive=False)
print(json.dumps(dict(archive=str(archive),files=len(files),bytes=archive.stat().st_size,sha256=sha(archive))))
PY
