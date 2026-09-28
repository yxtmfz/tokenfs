#!/usr/bin/env python3
"""Read-only descriptive analysis of report 28; no new performance observations."""
import argparse, hashlib, json
from pathlib import Path
from evidence_benchmark import percentile, dump


def analyze(root):
    root=Path(root);rows=[];hashes={}
    manifest=json.loads((root/'manifest.json').read_text())
    for b in manifest['spec']['blocks']:
        for name in b['variants']:
            case=root/b['id']/name
            for f in ['result.json','requests.json','policy-events.json','config.json']:
                p=case/f;hashes[str(p.relative_to(root))]=hashlib.sha256(p.read_bytes()).hexdigest()
            r=json.loads((case/'result.json').read_text());q=json.loads((case/'requests.json').read_text())
            m=r['metrics'];v=[x['response_seconds']*1000 for x in q]
            assert len(q)==576 and r['logical_bytes']==576*2*1024**2
            assert abs(percentile(v,.99)-r['request_p99_s']*1000)<1e-9
            rows.append(dict(block=b['id'],strategy=name,n=len(q),mib_s=r['effective_mib_s'],
                wall_s=r['job_wall_s'],drain_ms=r['drain_s']*1000,cpu_s=r['daemon_cpu_s'],
                p50_ms=percentile(v,.5),p95_ms=percentile(v,.95),p99_ms=percentile(v,.99),max_ms=max(v),
                above_30ms=sum(x>30 for x in v),remote_mib=m.get('read_remote_bytes',0)/1024**2,
                inflight_mib=m.get('read_inflight_bytes',0)/1024**2,
                copies=sum(m.get(k,0) for k in ['promote_count','cross_gpu_replica_create_count']),
                relocated=m.get('shared_placement_relocated',0),uncertainty_plans=m.get('measured_uncertainty_plans',0),
                top_requests=[dict(index=x['index'],key=x['key'],caller=x['caller'],response_ms=x['response_seconds']*1000,
                    open_read_close_ms=x['seconds']*1000) for x in sorted(q,key=lambda x:x['response_seconds'],reverse=True)[:8]]))
    assert len(rows)==12
    return dict(source='report28 completed batch',new_server_runs=0,descriptive_only=True,
        limitations=['No per-request tier/lock/copy timestamps in these speed runs: no causal phase attribution.',
                    'Single uniform run per strategy: requests are dependent observations, not independent repetitions.',
                    '30 ms exceedance and max are post-hoc descriptions, not replacements for frozen p99.'],
        input_sha256=hashes,rows=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();dump(a.output,analyze(a.input))
