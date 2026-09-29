import sys,json,tarfile
from pathlib import Path
root=Path(__file__).resolve().parent;tag='integrated-hpj-contention'
with tarfile.open(root/(tag+'-evidence.tar.gz')) as t:t.extractall(root/(tag+'-data'),filter='data')
sys.path.insert(0,str(root/(tag+'-source')/'scripts'))
from tail_diagnostic_analysis import analyze_case
out=[]
for c in sorted((root/(tag+'-data')/'development').glob('*/*')):
 if not (c/'result.json').exists():continue
 r=analyze_case(c);r['strategy']=c.name;out.append(r)
 print(c.name,{k:round(r['all_means'][k],3) for k in ['response_ms','daemon_open_ms','layout_wait_ms','metric_flush_ms','pread_ms']},'copymean',round(r['copy_mean_ms'],3),'write',round(r['copy_io_mean_ms'],3),'verify',round(r['copy_verify_mean_ms'],3))
(root/(tag+'-profile.json')).write_text(json.dumps(out,indent=2)+'\n')
