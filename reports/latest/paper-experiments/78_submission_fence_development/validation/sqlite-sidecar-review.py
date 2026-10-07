#!/usr/bin/env python3
"""Exercise preserved empty-WAL handling on disposable copies, never originals."""
from pathlib import Path
import tempfile,shutil,importlib.util,hashlib,json,sqlite3,contextlib
root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('verify78_sidecar',root/'verify78.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
original=root.parent/'hotspot-object77/evidence/development/public_toolagent-74802-r1/Full'
checks=[]
with tempfile.TemporaryDirectory(prefix='sidecar-test-',dir=root) as tmp:
    case=Path(tmp);shutil.copyfile(original/'state.db',case/'state.db')
    expected=v.archived_sql(original);assert v.archived_sql(case)==expected
    checks.append(dict(test='no_sidecar_main_db',passed=True))
    (case/'state.db-wal').write_bytes(b'');(case/'state.db-shm').write_bytes(bytes(32768))
    before=v.tree_hashes(case);assert v.archived_sql(case)==expected;assert v.tree_hashes(case)==before
    checks.append(dict(test='paired_empty_WAL_read_only_exact_and_unchanged',passed=True))
    (case/'state.db-wal').write_bytes(b'not-empty')
    try:v.archived_sql(case)
    except ValueError as e:assert 'nonempty WAL' in str(e)
    else:raise AssertionError('nonempty WAL accepted')
    checks.append(dict(test='nonempty_WAL_rejected',passed=True))
    (case/'state.db-wal').write_bytes(b'');(case/'state.db-shm').unlink()
    try:v.archived_sql(case)
    except ValueError as e:assert 'incomplete/unknown' in str(e)
    else:raise AssertionError('unpaired WAL accepted')
    checks.append(dict(test='unpaired_WAL_rejected',passed=True))
    (case/'state.db-shm').write_bytes(bytes(32768));(case/'state.db-journal').write_bytes(b'pending')
    try:v.archived_sql(case)
    except ValueError as e:assert 'incomplete/unknown' in str(e)
    else:raise AssertionError('unknown journal accepted')
    checks.append(dict(test='unknown_journal_rejected',passed=True))
# Demonstrate any mode=ro side effects only on a copied known-complete DB.
with tempfile.TemporaryDirectory(prefix='sqlite-ro-test-',dir=root) as tmp:
    case=Path(tmp);shutil.copyfile(original/'state.db',case/'state.db');before=v.tree_hashes(case)
    try:
        with contextlib.closing(sqlite3.connect((case/'state.db').resolve().as_uri()+'?mode=ro',uri=True)) as db:
            list(db.execute('SELECT name,value FROM metrics'))
        reproduction=dict(succeeded=True,before=before,after=v.tree_hashes(case),sizes={p.name:p.stat().st_size for p in case.iterdir()},db_unchanged=v.sha(case/'state.db')==before['state.db'])
    except sqlite3.Error as e:
        reproduction=dict(succeeded=False,error=str(e),before=before,after=v.tree_hashes(case),limitation='Local read-only reproduction not sufficient to establish server sidecar origin.')
answer=dict(passed=True,source_and_original_evidence_unchanged=True,server_access=False,checks=checks,readonly_side_effect_reproduction=reproduction,
            verifier_sha256=v.sha(root/'verify78.py'),collector_sha256=v.sha(root/'collect.sh'))
(root/'sqlite-sidecar-review.json').write_text(json.dumps(answer,indent=2)+'\n');print(json.dumps(answer))
