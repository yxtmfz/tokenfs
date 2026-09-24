from pathlib import Path
import sys,tempfile,shutil,json
sys.path.insert(0,'work/tokenfs-eval/scripts')
import shared_cache_pilot as study
src=Path('work/shared-cache-pilot-data/development');out=[]
with tempfile.TemporaryDirectory() as t:
 root=Path(t)/'data';shutil.copytree(src,root)
 p=next(root.glob('*/AnyReadyShare/result.json'));original=p.read_text();d=json.loads(original)
 d['logical_bytes']+=4096;p.write_text(json.dumps(d))
 out.append(dict(mutation='logical byte count',rejected=not study.audit(root)['passed']));p.write_text(original)
 p=next(root.glob('*/AnyReadyShare/config.json'));original=p.read_text();d=json.loads(original)
 d['policy']['peer_cache_reads']=False;p.write_text(json.dumps(d))
 out.append(dict(mutation='sharing switch',rejected=not study.audit(root)['passed']));p.write_text(original)
 p=next(root.glob('*/AnyReadyShare/requests.json'));original=p.read_text();d=json.loads(original)
 d[0]['completed_s']=1e6;p.write_text(json.dumps(d))
 out.append(dict(mutation='request timeline',rejected=not study.audit(root)['passed']));p.write_text(original)
 assert study.audit(root)['passed'] and all(x['rejected'] for x in out)
report=Path('work/tokenfs-eval/reports/latest/paper-experiments/17_shared_cache_pilot')
(report/'validation/tamper-check.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))
