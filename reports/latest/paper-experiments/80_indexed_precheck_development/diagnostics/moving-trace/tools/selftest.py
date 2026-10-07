#!/usr/bin/env python3
"""Local only: frozen80 binding plus historical77 parser and rejection tests.

Never executes a TokenFS binary, sends SSH, changes original evidence or calls
run(). Historical outputs are parser fixtures, not80performance measurements.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,shutil,sqlite3,sys,tempfile
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent

def module(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(p):return {str(x.relative_to(p)):sha(x) for x in p.rglob('*') if x.is_file()}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--historical77',type=Path,required=True);a=p.parse_args()
 driver=module('driver80',R/'tail-trace.py');an=module('analyzer80',R/'tail-trace-analysis.py')
 before=tree(a.historical77);source_before=tree(a.source_root);checks=[]
 args=argparse.Namespace(source_root=a.source_root,diagnostic_freeze=R/'tail-trace-freeze.json')
 checks.append({'name':'frozen80_config_input_identity','result':driver.selftest(args)})
 original=json.loads((R/'original-source-freeze.json').read_text());frozen=json.loads((R/'tail-trace-freeze.json').read_text())
 assert sha(R/'original-source-freeze.json')==frozen['original_freeze_sha256']
 assert original['source_hashes']==frozen['source_hashes'] and original['binary_sha256']==frozen['binary_sha256']
 assert original['specs']['development']==sha(a.source_root/'study-configs/indexed-precheck-development.json')
 checks.append({'name':'downloaded80_original_freeze_and_spec','passed':True})
 parsed={}
 for arm in ['Full','NoHotspot']:
  result=an.analyze_case(a.historical77/arm);parsed[arm]=result
  assert result['passed'] and result['requests']==1152 and result['top_count']==12
  assert all(x['physical_pread_ops'] is None and x['physical_pread_bytes'] is None for x in result['details'])
  checks.append({'name':'historical77_'+arm+'_parser_only','requests':result['requests'],'events':result['event_count'],'evidence_for80_speed':False})
 pair=an.paired_requests(parsed['Full'],parsed['NoHotspot'],'Historical77Full','Historical77NoHotspot')
 assert len(pair['all_requests'])==1152 and 12<=len(pair['top12_union'])<=24
 expected={x['index'] for arm in parsed.values() for x in arm['top12']}
 assert {x['index'] for x in pair['top12_union']}==expected
 assert all(x['left_physical_pread_ops'] is None and x['right_physical_pread_bytes'] is None for x in pair['all_requests'])
 checks.append({'name':'historical77_both_top12_union_parser_only','union_count':len(expected),'rows':1152,'physical_IO_unknown_null':True})
 def rejects(label,call):
  try:call()
  except (ValueError,AssertionError,KeyError) as e:checks.append({'name':label,'rejected':True,'reason':str(e)});return
  raise AssertionError('tamper accepted: '+label)
 with tempfile.TemporaryDirectory(prefix='trace80-selftest-') as tmp:
  t=Path(tmp);fixture=t/'case';shutil.copytree(a.historical77/'Full',fixture)
  trace=json.loads((fixture/'request-trace.json').read_text());original=json.dumps(trace)
  trace['dropped']=1;(fixture/'request-trace.json').write_text(json.dumps(trace));rejects('dropped_trace',lambda:an.analyze_case(fixture))
  trace=json.loads(original);next(e for e in trace['events'] if e['op']=='read' and e['bytes']>0)['bytes']+=1
  (fixture/'request-trace.json').write_text(json.dumps(trace));rejects('wrong_read_bytes',lambda:an.analyze_case(fixture))
  (fixture/'request-trace.json').write_text(original);(fixture/'state.db-wal').write_bytes(b'preserve-me')
  rejects('sidecar_parser_refusal',lambda:an.analyze_case(fixture));assert (fixture/'state.db-wal').read_bytes()==b'preserve-me'
  rejects('sidecar_schema_refusal',lambda:an.indexed_schema(fixture));assert (fixture/'state.db-wal').read_bytes()==b'preserve-me'
  schema=t/'schema';schema.mkdir()
  with sqlite3.connect(schema/'state.db') as db:
   db.executescript('CREATE TABLE files(logical_path TEXT PRIMARY KEY,gpu_id INTEGER,physical_path TEXT,size_bytes INTEGER,tier TEXT,state TEXT);CREATE TABLE local_replicas(logical_path TEXT,gpu_id INTEGER,physical_path TEXT,size_bytes INTEGER,state TEXT);')
   for sql in an.INDEX_DEFINITIONS.values():db.execute(sql)
  assert an.indexed_schema(schema)==an.INDEX_DEFINITIONS;checks.append({'name':'both_actual_index_definitions_synthetic_schema','passed':True})
  with sqlite3.connect(schema/'state.db') as db:db.execute('DROP INDEX idx_replicas_shared_precheck_ready')
  rejects('missing_index',lambda:an.indexed_schema(schema))
  with sqlite3.connect(schema/'state.db') as db:db.execute('CREATE INDEX idx_replicas_shared_precheck_ready ON local_replicas(gpu_id)')
  rejects('wrong_index_definition',lambda:an.indexed_schema(schema))
  wrong=json.loads(json.dumps(parsed['NoHotspot']));wrong['details'][0]['key']+=1
  rejects('same_ordinal_wrong_key',lambda:an.paired_requests(parsed['Full'],wrong))
 assert tree(a.historical77)==before and tree(a.source_root)==source_before
 result={'passed':True,'server_execution':False,'binary_execution':False,'source80_and_original77_evidence_unchanged':True,'checks':checks,'driver_hashes':driver.driver_receipts(),'diagnostic_freeze_sha256':sha(R/'tail-trace-freeze.json'),'historical77_identity':before}
 (R/'selftest-result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='historical77_identity'}))
if __name__=='__main__':main()
