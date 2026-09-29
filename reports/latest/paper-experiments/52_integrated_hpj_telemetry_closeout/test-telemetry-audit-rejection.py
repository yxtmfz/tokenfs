from pathlib import Path
import tempfile,shutil,json,subprocess,sys,sqlite3
p=Path(__file__).resolve().parent;tag='integrated-hpj-telemetry-reverse';results=[]
with tempfile.TemporaryDirectory(prefix='hpj-audit-') as tmp:
 root=Path(tmp);shutil.copytree(p/(tag+'-data'),root/(tag+'-data'));(root/(tag+'-source')).symlink_to(p/(tag+'-source'),target_is_directory=True)
 shutil.copy2(p/'review-telemetry-hpj.py',root/'review-telemetry-hpj.py')
 def run(label,should_pass):
  r=subprocess.run([sys.executable,str(root/'review-telemetry-hpj.py'),tag],capture_output=True,text=True)
  assert (r.returncode==0)==should_pass,(label,r.stderr[-800:]);results.append(dict(case=label,passed=True,accepted=r.returncode==0))
 run('untouched_complete_evidence',True)
 case=root/(tag+'-data/development/stationary_shared-3271-r1/Full');rp=case/'result.json';dbp=case/'state.db';original=rp.read_bytes();dboriginal=dbp.read_bytes();r=json.loads(original)
 key='request_cost_inflight_samples';assert r['metrics'].get('inflight_read_open_count',0)>0
 r['metrics'][key]+=1;rp.write_text(json.dumps(r))
 with sqlite3.connect(dbp) as db:db.execute('UPDATE metrics SET value=? WHERE name=?',(r['metrics'][key],key))
 db.close()
 run('matching_JSON_and_SQLite_false_inflight_cost_sample_count',False)
 rp.write_bytes(original)
 for suffix in ['-wal','-shm']:Path(str(dbp)+suffix).unlink(missing_ok=True)
 dbp.write_bytes(dboriginal)
 cp=root/(tag+'-data/development/comparisons.json');original=cp.read_bytes();r=json.loads(original);r[0]['gain_pct']+=1;cp.write_text(json.dumps(r));run('falsified_speed_gain',False);cp.write_bytes(original)
 run('restored_complete_evidence',True)
out=dict(passed=True,cases=results);(p/'telemetry-hpj-audit-rejection-tests.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
