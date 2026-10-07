set -eu
. /home/wjxt/aura-kv-tools/env.sh
root=/home/wjxt/tokenfs-indexed-precheck80-evidence
project=/home/wjxt/projects/tokenfs-indexed-precheck80-20261007
test "$(cat "$root/development.exit")" = 0
test "$(cat "$root/correctness.exit")" = 0
cd "$project"
# Do not run mode=ro source audit on originals again: it may create WAL/SHM.
# Successful source audit is already recorded; validate raw SQL immutably below.
mkdir -p "$root/provenance"
cp study-configs/indexed-precheck-freeze.json "$root/provenance/freeze.json"
cp build-release/Testing/Temporary/LastTest.log "$root/provenance/native-tests.log"
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Unexpected remaining TokenFS process'; exit 2; fi
python3 - <<'PY'
from pathlib import Path
from contextlib import closing
from collections import Counter
import tarfile,hashlib,json,sqlite3
r=Path('/home/wjxt/tokenfs-indexed-precheck80-evidence')
assert not any(str(r) in line for line in Path('/proc/mounts').read_text().splitlines())
load=lambda p:json.loads(p.read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record=lambda p:dict(bytes=p.stat().st_size,sha256=sha(p))
audit=load(r/'development/batch-audit.json')
assert audit['passed'] and audit['checked_runs']==audit['expected_runs']==24
content=load(r/'correctness/audit.json')
assert content['passed'] and content['cases']==6 and content['requests']==576
bundles={};preserved={};checked=0
for db in sorted(r.rglob('state.db')):
 if any(x.startswith('cache') for x in db.relative_to(r).parts):continue
 sidecars=sorted(db.parent.glob('state.db-*'))
 if sidecars:
  assert {p.name for p in sidecars}=={'state.db-wal','state.db-shm'},str(db)+': incomplete/unknown sidecars'
  assert (db.parent/'state.db-wal').stat().st_size==0,str(db)+': nonempty WAL requires separate review'
  assert (db.parent/'state.db-shm').stat().st_size==32768,str(db)+': unexpected SHM size'
 files=[db]+sidecars
 before={str(p.relative_to(r)):record(p) for p in files}
 result=load(db.parent/'result.json');requests=load(db.parent/'requests.json')
 with closing(sqlite3.connect(db.resolve().as_uri()+'?mode=ro&immutable=1',uri=True)) as con:
  assert list(con.execute('PRAGMA quick_check'))==[('ok',)],str(db)+': SQLite check failed'
  metrics=dict(con.execute('SELECT name,value FROM metrics'))
  access={(p,g):n for p,g,n in con.execute('SELECT logical_path,gpu_id,read_count FROM gpu_access')}
 assert metrics==result['metrics'] and result['metrics_snapshot']=='after_daemon_shutdown',str(db)+': immutable metrics mismatch'
 assert access==dict(Counter((f"/gpu0/shard-{row['key']:06d}.tokens",row['caller']) for row in requests)),str(db)+': immutable access mismatch'
 assert metrics['read_release_count']==metrics['read_open_count']==len(requests)
 assert metrics.get('background_submitted',0)==metrics.get('background_completed',0)
 after={str(p.relative_to(r)):record(p) for p in files};assert before==after,'SQL originals changed'
 preserved.update(before)
 bundles[str(db.relative_to(r))]=dict(files=before,sidecar_mode='paired_empty_wal_preserved' if sidecars else 'no_sidecars',immutable_sql_matches=True)
 checked+=1
assert checked==30,checked
all_sidecars={str(p.relative_to(r)) for p in r.rglob('state.db-*')}
assert all_sidecars=={name for name in preserved if Path(name).name!='state.db'},'unaccounted sidecars'
receipt=dict(format=1,policy='Preserve main database and every original sidecar. Accept only absent sidecars or a complete pair with zero-byte WAL and 32768-byte SHM; read main DB immutably, never checkpoint or delete.',checked_databases=checked,sidecar_files=len(all_sidecars),bundles=bundles,files=preserved,original_sql_files_unchanged=True)
receipt_path=r/'provenance/sqlite-sidecars.json'
if receipt_path.exists():assert load(receipt_path)==receipt,'different existing sidecar receipt'
else:receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
p=Path('/home/wjxt/tokenfs-indexed-precheck80-evidence.tar.gz')
with tarfile.open(p,'w:gz') as t:
 for f in sorted(r.rglob('*')):
  if f.is_file() and (f.suffix in ['.json','.db','.log','.exit','.sh'] or f.name in ['state.db-wal','state.db-shm']) and not any(x.startswith('cache') for x in f.relative_to(r).parts):
   t.add(f,arcname=str(f.relative_to(r)))
assert {name:record(r/name) for name in preserved}==preserved,'original SQL files changed during tar'
with tarfile.open(p) as t:
 entries={m.name:m for m in t.getmembers() if m.isfile()}
 for name,expected in preserved.items():
  assert name in entries
  data=t.extractfile(entries[name]).read()
  assert len(data)==expected['bytes'] and hashlib.sha256(data).hexdigest()==expected['sha256'],'tar omitted/changed SQL component'
print(json.dumps(dict(sqlite_databases=checked,sidecar_files=len(all_sidecars),sidecars_preserved=True)))
print(hashlib.sha256(p.read_bytes()).hexdigest())
PY
