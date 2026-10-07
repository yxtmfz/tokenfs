#!/usr/bin/env python3
"""Local preparation: bind external tools to completed80 source and binary."""
from pathlib import Path
import hashlib,importlib.util,json,sys,argparse
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True);p.add_argument('--source-archive',type=Path,required=True);p.add_argument('--original-freeze',type=Path,required=True);a=p.parse_args()
 spec=importlib.util.spec_from_file_location('trace_driver',R/'tail-trace.py');d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
 study,_=d.source_modules(a.source_root)
 orig=d.read(a.original_freeze);hashes={n:d.sha(a.source_root/n) for n in study.SOURCES}
 d.require(len(hashes)==355 and orig['source_hashes']==hashes,'completed80 source identity')
 d.require(orig['specs']['development']==d.sha(a.source_root/'study-configs/indexed-precheck-development.json'),'completed80 spec')
 events=study.trace(d.SPEC);objects=d.expected_objects(events)
 frozen={'diagnosis_only':True,'performance_evidence':False,'spec':d.SPEC,'order':d.ORDER,'cpu_affinity':d.CPU_AFFINITY,'source_hashes':hashes,'source_archive_sha256':d.sha(a.source_archive),'binary_sha256':orig['binary_sha256'],'trace_sha256':d.digest(events),'objects_sha256':d.digest(objects),'driver_hashes':d.driver_receipts(),'original_freeze_sha256':d.sha(a.original_freeze),'original_spec_hashes':orig['specs'],'binary_provenance':'Completed80 downloaded original source/binary/spec freeze; run requires the same freeze and actual binary hash.'}
 (R/'tail-trace-freeze.json').write_text(json.dumps(frozen,indent=2)+'\n')
 (R/'planned-input.json').write_text(json.dumps({'status':'not_executed','spec':d.SPEC,'order':d.ORDER,'cpu_affinity':d.CPU_AFFINITY,'events':events,'object_hashes':objects},indent=2)+'\n')
 configs={name:d.config(study,name,Path('/PLANNED/trace80')/name,Path('/PLANNED/remote')) for name in d.ORDER}
 (R/'planned-configs.json').write_text(json.dumps({'status':'not_executed','arms':configs},indent=2)+'\n')
 print(json.dumps({'status':'not_executed','sources':len(hashes),'requests':len(events),'objects':len(objects),'binary':orig['binary_sha256'],'freeze':d.sha(R/'tail-trace-freeze.json')}))
if __name__=='__main__':main()
