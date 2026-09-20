#!/usr/bin/env python3
"""Versioned, speed-first development/confirmation study; no outcome-based filtering."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shutil
import statistics
import subprocess
import time

from evidence_benchmark import MIB, config_for as old_config, run_case, dump, sha
from evidence_report import interval,paired_p,holm

VARIANTS={
 'RemoteOnly':None,'LRU-equal':None,'LFU-equal':None,'AURA-core':None,
 'RecentLFU-admit':{'measured_cost':False,'measured_size_aware':False,'measured_frequency_admission':True,'measured_shift_reset':False},
 'AURA-adaptive':{},'AURA-no-admission':{'measured_admission':False},
 'AURA-no-aging':{'measured_aging':False},'AURA-no-shift':{'measured_shift_reset':False},'AURA-no-value':{'measured_value_victim':False},
 'AURA-no-size':{'measured_size_aware':False},'AURA-no-cost':{'measured_cost':False},
 'AURA-no-joint':{'measured_admission':False,'measured_value_victim':False},
 'AURA-synchronous':{'async_promote_on_read':False,'async_cross_gpu_replica':False},
}

def digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def configuration(name,case,remote,quota,direct,window=128,schema=3):
 cfg=old_config(name if VARIANTS[name] is None else 'AURA-core',case,remote,quota,direct)
 if VARIANTS[name] is not None:
  cfg['policy'].update(measured_policy=True,measured_window=window,measured_aging=True,
      measured_admission=True,measured_cost=True,measured_value_victim=True,measured_size_aware=True,measured_frequency_admission=False,measured_shift_reset=True,measured_shift_window=8)
  cfg['policy'].update(VARIANTS[name])
  if schema==1:cfg['policy'].pop('measured_frequency_admission',None)
  if schema<3:
   cfg['policy'].pop('measured_shift_reset',None);cfg['policy'].pop('measured_shift_window',None)
 return cfg

def synthetic(scenario,seed,requests,shard_mib):
 rng=random.Random(seed);events=[];sizes={i:shard_mib for i in range(64)}
 if scenario=='mixed_fit':sizes={i:shard_mib*(1+i%4) for i in range(64)}
 for i in range(requests):
  if scenario=='stable':key=rng.randrange(4) if rng.random()<.85 else rng.randrange(4,64)
  elif scenario=='shift':
   phase=min(3,i*4//requests);key=phase*8+rng.randrange(4) if rng.random()<.85 else rng.randrange(32,64)
  elif scenario=='scan':key=rng.randrange(4) if i%64<44 else 4+i%60
  elif scenario=='mixed_fit':key=rng.randrange(12) if rng.random()<.8 else rng.randrange(12,64)
  elif scenario=='uniform':key=rng.randrange(64)
  else:raise ValueError('unknown synthetic scenario')
  events.append({'index':i,'key':key,'caller':0,'bytes':sizes[key]*MIB})
 return sizes,events,{'kind':'synthetic','generator':'measured-v1','seed':seed}

def application(path,split,offset,requests,shard_mib,paced=False):
 raw=[json.loads(line) for line in path.read_text().splitlines()]
 cut=len(raw)//5
 # The first fifth is development only; the remaining records are held out.
 subset=raw[:cut] if split=='development' else raw[cut:]
 if offset>=len(subset):raise ValueError('offset outside split')
 keys={};events=[];first=None;used_requests=0
 for j,row in enumerate(subset[offset:],start=offset):
  if first is None:first=row['timestamp']
  used_requests+=1
  for block in row['hash_ids']:
   key=keys.setdefault(str(block),len(keys))
   e={'index':len(events),'key':key,'caller':0,'bytes':shard_mib*MIB,'source_request':j+(0 if split=='development' else cut),'source_hash':str(block),'source_arrival_ms':row['timestamp']-first}
   if paced:e['release_s']=(row['timestamp']-first)/1000
   events.append(e)
   if len(events)>=requests:break
  if len(events)>=requests:break
 if len(events)!=requests:raise ValueError('not enough blocks in source slice')
 return {v:shard_mib for v in keys.values()},events,dict(kind='Mooncake-FAST25',file=path.name,sha256=sha(path),split=split,
     source_request_offset=offset,source_requests_used=used_requests,block_count=requests,block_tokens=512,
     payload='normalized synthetic bytes per original block identity; not a model KV byte-size claim',
     arrival_mode='original timestamps, single serialized client' if paced else 'order-preserving saturated block replay; original arrivals retained but not paced')

def check_mount(remote,verify):
 mount=json.loads(subprocess.check_output(['findmnt','-J','--target',str(remote)],text=True))['filesystems'][0]
 if verify:return {'mount':mount,'verification_only':True}
 import re
 found=re.fullmatch(r'/dev/(nvme[0-9]+)n[0-9]+(?:p[0-9]+)?',mount['source'])
 if not found:raise RuntimeError('performance requires actual NVMe/TCP mount')
 ctl=Path('/sys/class/nvme')/found.group(1)
 identity={k:(ctl/k).read_text().strip() for k in ['transport','address','subsysnqn']}
 if identity['transport']!='tcp' or identity['subsysnqn']!='nqn.2026-09.local.aura-kv:remote-cn7' or 'traddr=28.10.10.13' not in identity['address'].split(','):
  raise RuntimeError('unexpected NVMe/TCP identity')
 return {'mount':mount,'nvme_identity':identity}

def execute(args):
 spec=json.loads(args.spec.read_text());root=args.output.resolve();remote=args.remote_root.resolve()
 if spec['stage'] not in ['development','confirmation','correctness']:raise ValueError('stage required')
 if bool(args.verify)!=(spec['stage']=='correctness'):raise ValueError('verification and timing are separate batches')
 build=(args.binary.resolve().parent/'CMakeCache.txt').read_text()
 if 'CMAKE_BUILD_TYPE:STRING=Release' not in build:raise ValueError('Release required')
 identity=check_mount(remote,args.verify)
 root.mkdir(parents=True,exist_ok=False);data_root=remote/('measured-'+root.name);data_root.mkdir(exist_ok=False)
 source_root=Path(__file__).resolve().parents[1]
 manifest=dict(spec=spec,spec_sha256=digest(spec),binary_sha256=sha(args.binary),build_type='Release',
     source_hashes={str(p.relative_to(source_root)):sha(p) for p in [source_root/'src/main.cpp',source_root/'src/measured_policy.h',source_root/'scripts/measured_study.py',source_root/'scripts/evidence_benchmark.py']},
     configuration_schema=3,output=str(root),remote_data=str(data_root),verify=args.verify,backend_direct=not args.verify or args.backend_direct,
     created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),**identity)
 dump(root/'manifest.json',manifest)
 for block_spec in spec['blocks']:
  block=root/block_spec['id'];block.mkdir();data=data_root/block.name;(data/'gpu0').mkdir(parents=True)
  scenario=block_spec['scenario'];seed=block_spec['seed'];requests=block_spec['requests'];shard=block_spec['shard_mib']
  if scenario.startswith('mooncake_'):
   sizes,events,origin=application(args.trace_dir/(scenario.removeprefix('mooncake_')+'_trace.jsonl'),
      'development' if spec['stage'] in ['development','correctness'] else 'confirmation',block_spec['source_offset'],requests,shard,block_spec.get('paced',False))
  else:sizes,events,origin=synthetic(scenario,seed,requests,shard)
  expected={}
  for key,mib in sizes.items():
   path=data/'gpu0'/f'shard-{key:06d}.tokens';payload=random.Random(seed*100000+key).randbytes(MIB)
   with path.open('wb') as f:
    for _ in range(mib):f.write(payload)
    f.flush();os.fsync(f.fileno())
   expected[str(key)]=sha(path)
  dump(block/'trace.json',events);dump(block/'objects.json',{'sizes_mib':sizes,'sha256':expected})
  order=block_spec['variants'].copy();random.Random(seed).shuffle(order)
  frozen={'spec':block_spec,'trace_sha256':digest(events),'origin':origin,'order':order,'objects_sha256':digest(expected),'unique_objects':len(sizes),'working_set_mib':sum(sizes.values())}
  dump(block/'input.json',frozen)
  for name in order:
   case=block/name;cfg=configuration(name,case,data,block_spec['quota_mib'],manifest['backend_direct'],block_spec.get('window',128))
   result=run_case(args.binary.resolve(),case,data,name,events,expected,block_spec['quota_mib'],args.verify,manifest['backend_direct'],configuration=cfg)
   print(json.dumps({'block':block.name,'strategy':name,'mib_s':result['effective_mib_s'],'wall_s':result['job_wall_s'],'copies_mib':sum(result['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB,'rejects':{k:v for k,v in result['metrics'].items() if k.startswith('measured_precheck')}}),flush=True)
  # Only our generated canonical payloads are removed; their deterministic seed/hash remains.
  # Avoid accumulating hundreds of GiB on the shared test namespace.
  if args.remove_generated_data:shutil.rmtree(data)
 result=audit(root)
 if not result["passed"]:raise RuntimeError("batch audit failed; see batch-audit.json")


def audit(root):
 m=json.loads((root/'manifest.json').read_text());errors=[];seen=set();checked=0
 if (root/'INVALIDATED.json').exists():errors.append('explicitly invalidated')
 if digest(m['spec'])!=m['spec_sha256']:errors.append('spec hash changed')
 if m['build_type']!='Release':errors.append('not Release')
 for bs in m['spec']['blocks']:
  b=root/bs['id'];order=bs['variants'].copy();random.Random(bs['seed']).shuffle(order)
  if not (b/'input.json').exists():errors.append(bs['id']+': missing inputs');continue
  frozen=json.loads((b/'input.json').read_text());trace=json.loads((b/'trace.json').read_text());objects=json.loads((b/'objects.json').read_text())
  if frozen['spec']!=bs or frozen['order']!=order:errors.append(bs['id']+': block spec/order')
  if digest(trace)!=frozen['trace_sha256'] or digest(objects['sha256'])!=frozen['objects_sha256']:errors.append(bs['id']+': input integrity')
  if len(trace)!=bs['requests']:errors.append(bs['id']+': trace size')
  if not bs['scenario'].startswith('mooncake_') and synthetic(bs['scenario'],bs['seed'],bs['requests'],bs['shard_mib'])[1]!=trace:errors.append(bs['id']+': generator differs')
  for name in order:
   seen.add((bs['id'],name));case=b/name
   if not (case/'result.json').exists():errors.append(f'{bs["id"]}/{name}: missing result');continue
   r=json.loads((case/'result.json').read_text());rows=json.loads((case/'requests.json').read_text());cfg=json.loads((case/'config.json').read_text())
   reference=configuration(name,Path(m['output'])/bs['id']/name,Path(m['remote_data'])/bs['id'],bs['quota_mib'],m['backend_direct'],bs.get('window',128),m.get('configuration_schema',1))
   if cfg!=reference:errors.append(f'{bs["id"]}/{name}: config differs')
   if len(rows)!=len(trace) or any(any(row.get(k)!=v for k,v in e.items()) for row,e in zip(rows,trace)):errors.append(f'{bs["id"]}/{name}: trace mismatch')
   total=sum(e['bytes'] for e in trace);metrics=r['metrics'];problems=[]
   if r['strategy']!=name or r['status']!='ok' or r['verify_every_request']!=m['verify']:problems.append('identity/status')
   if total!=r['logical_bytes'] or total!=metrics.get('read_bytes',0) or len(trace)!=metrics.get('read_open_count',0):problems.append('request accounting')
   if total!=metrics.get('read_local_bytes',0)+metrics.get('read_remote_bytes',0):problems.append('source accounting')
   for gpu in range(3):
    if sum(e['bytes'] for e in trace if e['caller']==gpu)!=metrics.get(f'qos_gpu{gpu}_read_bytes',0):problems.append('GPU accounting')
   if metrics.get('background_submitted',0)!=metrics.get('background_completed',0):problems.append('background incomplete')
   if any(v for k,v in metrics.items() if k.endswith('error_count')):problems.append('error counter')
   if max(r['retained_cache_bytes'])>bs['quota_mib']*MIB:problems.append('quota')
   if not all(math.isfinite(r[k]) and r[k]>0 for k in ['job_wall_s','effective_mib_s']) or abs(r['effective_mib_s']-total/MIB/r['job_wall_s'])>1e-8:problems.append('time/rate')
   if m['verify'] and any(row.get('sha256')!=objects['sha256'][str(row['key'])] for row in rows):problems.append('content hash')
   if problems:errors.append(f'{bs["id"]}/{name}: '+', '.join(problems))
   checked+=1
 actual={(p.parent.parent.name,p.parent.name) for p in root.glob('*/*/result.json')}
 if actual-seen:errors.append('unexpected cases')
 if list(root.rglob('failure.json')):errors.append('failed cases preserved')
 answer={'passed':not errors,'checked_runs':checked,'expected_runs':sum(len(b['variants']) for b in m['spec']['blocks']),'errors':errors}
 dump(root/'batch-audit.json',answer);return answer


def report(root):
 status=audit(root)
 if not status['passed']:raise ValueError('audit failed')
 m=json.loads((root/'manifest.json').read_text())
 if m['verify']:raise ValueError('verification timings cannot be performance evidence')
 groups={};summaries=[];comparisons=[]
 for bs in m['spec']['blocks']:
  key=(bs['scenario'],bs['quota_mib'],bs.get('paced',False),bs['requests'],bs['shard_mib'],bs.get('window',128));groups.setdefault(key,[]).append(bs)
 for (scene,quota,paced,requests,shard,window),blocks in groups.items():
  names=list(dict.fromkeys(n for b in blocks for n in b['variants']))
  for name in names:
   results=[json.loads((root/b['id']/name/'result.json').read_text()) for b in blocks if name in b['variants']]
   summaries.append(dict(scenario=scene,quota_mib=quota,paced=paced,requests=requests,shard_mib=shard,window=window,strategy=name,n=len(results),mean_wall_s=statistics.mean(r['job_wall_s'] for r in results),mean_mib_s=statistics.mean(r['effective_mib_s'] for r in results),mean_copy_mib=statistics.mean(sum(r['metrics'].get(k,0) for k in ['promote_bytes','cross_gpu_replica_create_bytes'])/MIB for r in results),mean_cpu_s=statistics.mean(r.get('daemon_cpu_s',0) for r in results),mean_rss_kib=statistics.mean(r.get('daemon_peak_rss_kib',0) or 0 for r in results)))
  for name in names:
   if name=='AURA-adaptive':continue
   pairs=[]
   for b in blocks:
    if name in b['variants'] and 'AURA-adaptive' in b['variants']:
     a=json.loads((root/b['id']/'AURA-adaptive/result.json').read_text());other=json.loads((root/b['id']/name/'result.json').read_text());pairs.append((a,other))
   if not pairs:continue
   logs=[math.log(a['job_wall_s']/b['job_wall_s']) for a,b in pairs]
   comparisons.append(dict(scenario=scene,quota_mib=quota,paced=paced,requests=requests,shard_mib=shard,window=window,baseline=name,n=len(pairs),time_ratio=math.exp(statistics.mean(logs)),ci95=interval(logs,math.exp),p_raw=paired_p(logs),p_holm=None,
      family='primary' if name in ['LRU-equal','LFU-equal','RecentLFU-admit'] else name,
      with_drain_ratio=math.exp(statistics.mean(math.log(a['completed_with_background_s']/b['completed_with_background_s']) for a,b in pairs))))
 for family in {r['family'] for r in comparisons}:holm([r for r in comparisons if r['family']==family])
 for r in comparisons:
  r['verdict']='development / no confirmatory claim'
  if m['spec']['stage']=='confirmation':
   r['verdict']='uncertain'
   if r['n']>=10 and r['p_holm']<.05 and r['ci95'][1]<1:r['verdict']='faster'
   elif r['n']>=10 and r['p_holm']<.05 and r['ci95'][0]>1:r['verdict']='slower'
 dump(root/'summary.json',summaries);dump(root/'paired-comparisons.json',comparisons)
 return summaries,comparisons

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('operation',choices=['run','audit','report']);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--spec',type=Path);p.add_argument('--binary',type=Path);p.add_argument('--remote-root',type=Path);p.add_argument('--trace-dir',type=Path)
 p.add_argument('--verify',action='store_true');p.add_argument('--backend-direct',action='store_true');p.add_argument('--remove-generated-data',action='store_true')
 args=p.parse_args()
 if args.operation=='run':execute(args)
 elif args.operation=='audit':
  result=audit(args.output);print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
 else:report(args.output)
