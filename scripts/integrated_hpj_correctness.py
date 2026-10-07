#!/usr/bin/env python3
"""Small content-check sweep; its hash-instrumented times are NOT speed evidence."""
import argparse,importlib,json,random,shutil,sys,os
from pathlib import Path
from evidence_benchmark import run_case,sha,dump,MIB
from measured_study import check_mount

def run(a):
 repo=Path(__file__).resolve().parents[1];study=importlib.import_module(a.study)
 frozen=json.loads(a.freeze.read_text());binary=a.binary.resolve();remote=a.remote_root.resolve();out=a.output.resolve()
 assert frozen['source_hashes']=={p:sha(repo/p) for p in study.SOURCES}
 assert frozen['binary_sha256']==sha(binary)
 assert 'CMAKE_BUILD_TYPE:STRING=Release' in (binary.parent/'CMakeCache.txt').read_text()
 identity=check_mount(remote,False)
 out.mkdir(parents=True,exist_ok=False);data=remote/'content-check-3401';(data/'gpu0').mkdir(parents=True,exist_ok=False)
 b=dict(id='content-check',scenario='moving_shared',seed=3401,requests=96,shard_mib=2,quota_mib=24)
 events=study.trace(b);expected={}
 for key in sorted({e['key'] for e in events}):
  p=data/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(340100000+key).randbytes(MIB)
  with p.open('wb') as f:f.write(payload*2);f.flush();os.fsync(f.fileno())
  expected[str(key)]=sha(p)
 dump(out/'trace.json',events);dump(out/'objects.json',expected)
 dump(out/'manifest.json',dict(stage='content_correctness_not_speed',study=a.study,spec=b,variants=study.VARIANTS,output=str(out),remote_data=str(data),source_hashes=frozen['source_hashes'],binary_sha256=sha(binary),driver_sha256=sha(Path(__file__)),**identity))
 for v in study.VARIANTS:
  case=out/v;cfg=study.configuration(v,case,data,24,True)
  assert not cfg['policy']['profile_control_path'] and not cfg['policy'].get('request_trace_path')
  r=run_case(binary,case,data,v,events,expected,24,True,True,configuration=cfg)
  assert r['status']=='ok' and r['verify_every_request']
  rows=json.loads((case/'requests.json').read_text())
  assert len(rows)==96 and all(x['sha256']==expected[str(x['key'])] for x in rows)
  assert not any(x for k,x in r['metrics'].items() if k.endswith('error_count'))
  assert all(n<=g['local_quota_mib']*MIB for n,g in zip(r['retained_cache_bytes'],cfg['gpus']))
  print(json.dumps(dict(strategy=v,verified_requests=len(rows),passed=True)),flush=True)
 dump(out/'audit.json',dict(passed=True,cases=5,requests=480,interpretation='Every returned request SHA256 checked; timings include hashing and are excluded from speed comparisons.'))
 shutil.rmtree(data)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for k in ['binary','freeze','output','remote-root']:p.add_argument('--'+k,type=Path,required=True)
 p.add_argument('--study',default='integrated_hpj_guarded_study')
 run(p.parse_args())
