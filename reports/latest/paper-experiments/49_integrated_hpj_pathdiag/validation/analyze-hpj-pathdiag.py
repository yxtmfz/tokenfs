import sys,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'integrated-hpj-pathdiag-source/scripts'))
from tail_diagnostic_analysis import analyze_case
base=root/'integrated-hpj-pathdiag-data/development';m=json.loads((base/'manifest.json').read_text());out=[]
for b in m['spec']['blocks']:
 for v in b['variants']:
  case=base/b['id']/v;a=analyze_case(case);r=json.loads((case/'result.json').read_text());metrics=r['metrics']
  strata=[]
  for tier in ['local','remote','inflight']:
   rows=[x for x in a['request_details'] if x['tier']==tier]
   strata.append(dict(tier=tier,n=len(rows),mean_response_ms=statistics.mean(x['response_ms'] for x in rows) if rows else None))
  a.pop('request_details');a.update(block=b['id'],strategy=v,strata_all_tiers=strata,cpu_s=r['daemon_cpu_s'],shared_plan_total_ms=metrics.get('shared_plan_latency_us_total',0)/1000)
  out.append(a)
  print(b['scenario'],v,round(a['diagnostic_mib_s'],2),'p99',round(a['p99_ms'],3),'copies',a['copy_count'],'means', {k:round(a['all_means'][k],3) for k in ['daemon_open_ms','layout_wait_ms','pread_ms','daemon_read_ms','release_ms','metric_flush_ms','release_wait_ms','ipc_scheduling_ms']},'tail',{k:round(a['tail_means'][k],3) for k in ['daemon_open_ms','layout_wait_ms','pread_ms','metric_flush_ms','copy_overlap_ms']})
(root/'integrated-hpj-pathdiag-profile.json').write_text(json.dumps(out,indent=2)+'\n')
