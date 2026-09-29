import json,sys,math
from pathlib import Path
p=Path(__file__).resolve().parent
sys.path.insert(0,str(p/'integrated-hpj-readpath-source/scripts'))
from evidence_benchmark import percentile
load=lambda p:json.loads(p.read_text());tags=['integrated-hpj-readpath','integrated-hpj-readpath-reverse']
d=[p/(t+'-data')/'development' for t in tags];ms=[load(x/'manifest.json') for x in d]
assert ms[0]['binary_sha256']==ms[1]['binary_sha256']
assert all(ms[1]['source_hashes'].get(k)==v for k,v in ms[0]['source_hashes'].items())
assert ms[0]['spec']==ms[1]['spec']
variants=ms[0]['spec']['blocks'][0]['variants'];rows=[];comparisons=[]
for b in ms[0]['spec']['blocks']:
 assert load(d[0]/b['id']/'input.json')['order']==list(reversed(load(d[1]/b['id']/'input.json')['order']))
 assert load(d[0]/b['id']/'trace.json')==load(d[1]/b['id']/'trace.json')
 arm={}
 for v in variants:
  rs=[load(x/b['id']/v/'result.json') for x in d];requests=sum([load(x/b['id']/v/'requests.json') for x in d],[])
  total=sum(r['logical_bytes'] for r in rs)/1048576
  row=dict(block=b['id'],scenario=b['scenario'],strategy=v,n=2,mib_s=total/sum(r['job_wall_s'] for r in rs),drain_mib_s=total/sum(r['completed_with_background_s'] for r in rs),pooled_p99_ms=1000*percentile([x['response_seconds'] for x in requests],.99),per_run_mib_s=[r['effective_mib_s'] for r in rs],per_run_p99_ms=[r['request_p99_s']*1000 for r in rs],remote_mib=[r['metrics']['read_remote_bytes']/1048576 for r in rs],inflight_mib=[r['metrics'].get('read_inflight_bytes',0)/1048576 for r in rs],copies=[sum(r['metrics'].get(k,0) for k in ['promote_count','cross_gpu_replica_create_count']) for r in rs])
  rows.append(row);arm[v]=row
 for v in variants[1:]:
  x,y=arm['Full'],arm[v];pairs=[next(z for z in load(q/'comparisons.json') if z['block']==b['id'] and z['baseline']==v) for q in d]
  comparisons.append(dict(block=b['id'],scenario=b['scenario'],baseline=v,gain_pct=100*(x['mib_s']/y['mib_s']-1),drain_gain_pct=100*(x['drain_mib_s']/y['drain_mib_s']-1),pooled_p99_change_pct=100*(x['pooled_p99_ms']/y['pooled_p99_ms']-1),per_run_gain_pct=[z['gain_pct'] for z in pairs],per_run_p99_change_pct=[z['p99_change_pct'] for z in pairs],passes_both_orders=all(z['pilot_screen'] for z in pairs),mechanisms_active_both_orders=all(z['mechanism_active'] for z in pairs)))
out=dict(passed=True,binary_sha256=ms[0]['binary_sha256'],runs=30,requests=17280,rows=rows,comparisons=comparisons,all_gates_both_orders=all(x['passes_both_orders'] for x in comparisons),limits='Two orders of known development inputs; descriptive rates, no significance or physical GPU evidence. Includes ALL runs, not selected winners.')
(p/'readpath-hpj-final-rollup.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
