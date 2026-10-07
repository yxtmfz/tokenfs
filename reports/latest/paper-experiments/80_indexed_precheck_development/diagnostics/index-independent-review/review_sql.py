from pathlib import Path
import hashlib,json,re,sqlite3
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'tokenfs-eval/src/main.cpp'
STATE=ROOT.parent/'hotspot-precheck79/evidence/development/public_toolagent-74802-r1/Full/state.db'
s=SOURCE.read_text();query=re.search(r'kReadyResidentBytesSql="([^"]+)";',s).group(1)
chunk=s[s.index('  bool CreateSharedPrecheckIndexes()'):s.index('  bool TryEmptyResidentState()')]
ddl=re.findall(r'Exec\("(CREATE INDEX[^\"]+)"\)',chunk)
assert len(ddl)==2
beforehash=hashlib.sha256(STATE.read_bytes()).hexdigest()
con=sqlite3.connect('file:'+str(STATE.resolve())+'?mode=ro',uri=True)
def fresh():
 db=sqlite3.connect(':memory:',isolation_level=None);con.backup(db);return db

def plan(db):return [row[3] for row in db.execute('EXPLAIN QUERY PLAN '+query)]
def rows(db):return sorted(db.execute(query).fetchall())
def indices(db):return list(db.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND name LIKE '%shared_precheck%'").fetchall())
results={}
x=fresh();old=rows(x);pre=plan(x);x.execute('BEGIN IMMEDIATE')
for q in ddl:x.execute(q)
x.execute('COMMIT')
assert rows(x)==old
results['real79_full_db_equivalence']={'before_plan':pre,'after_plan':plan(x),'same_rows':True,'row_count':len(old),'files_count':x.execute('SELECT COUNT(*) FROM files').fetchone()[0],'replica_count':x.execute('SELECT COUNT(*) FROM local_replicas').fetchone()[0],'indexes':indices(x)}
# Re-running setup is idempotent and data remains equal.
x.execute('BEGIN IMMEDIATE')
for q in ddl:x.execute(q)
x.execute('COMMIT');assert rows(x)==old;results['idempotent']=True
# Real second-statement SQL failure: first new index must roll back too.
x=fresh();x.execute('CREATE TABLE idx_replicas_shared_precheck_ready(x INTEGER)');x.execute('BEGIN IMMEDIATE')
try:
 for q in ddl:x.execute(q)
 raise AssertionError('expected schema conflict')
except sqlite3.DatabaseError as e:
 error=str(e);x.execute('ROLLBACK')
assert not x.in_transaction and indices(x)==[]
assert rows(x)==old
results['second_create_failure']={'error':error,'rollback_both_new_indexes':True,'autocommit_restored':not x.in_transaction,'query_unchanged':True}
# Existing index remains after failure, as transaction rollback must not drop prior schema.
x=fresh();x.execute(ddl[0]);x.execute('CREATE TABLE idx_replicas_shared_precheck_ready(x INTEGER)');x.execute('BEGIN IMMEDIATE')
try:
 for q in ddl:x.execute(q)
 raise AssertionError('expected schema conflict')
except sqlite3.DatabaseError:x.execute('ROLLBACK')
assert len(indices(x))==1 and rows(x)==old
results['second_create_failure_prior_first_index_preserved']=True
# IF NOT EXISTS can accept wrong existing definitions; results stay equal but plan is not promised.
x=fresh();x.execute("CREATE INDEX idx_files_shared_precheck_local ON files(updated_at)")
x.execute("CREATE INDEX idx_replicas_shared_precheck_ready ON local_replicas(created_at)")
x.execute('BEGIN IMMEDIATE')
for q in ddl:x.execute(q)
x.execute('COMMIT');assert rows(x)==old
results['same_name_wrong_definition']={'setup_sql_succeeds':True,'rows_unchanged':True,'indexes':indices(x),'plan':plan(x),'limitation':'CREATE IF NOT EXISTS alone cannot certify the intended covering plan; validate or label setup rather than plan.'}
assert hashlib.sha256(STATE.read_bytes()).hexdigest()==beforehash
results['sqlite_version']=sqlite3.sqlite_version
results['source_sha256']=hashlib.sha256(SOURCE.read_bytes()).hexdigest();results['read_only_evidence_sha256']=beforehash
results['query']=query;results['ddl']=ddl;results['evidence_unchanged']=True
(ROOT/'sql-review.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
