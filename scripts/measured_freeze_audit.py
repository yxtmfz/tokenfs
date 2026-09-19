"""Offline provenance and timing checks for the three predeclared B3 batches."""
import argparse,hashlib,json,math,sys
from pathlib import Path
repo=Path(__file__).resolve().parents[1];sys.path.insert(0,str(repo/'scripts'))
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence-root',type=Path,required=True,help='Extracted cn7 directory')
p.add_argument('--trace-dir',type=Path,required=True,help='Pinned original Mooncake source files')
p.add_argument('--freeze',type=Path,default=repo/'study-configs/measured-b3-freeze.json')
args=p.parse_args()
from measured_study import application,digest
freeze=json.loads(args.freeze.read_text())
root=args.evidence_root;errors=[];cases=0;public=0
context=json.loads((root/'measured-b3-confirmation-execution-context.json').read_text())
if context['freeze_sha256']!=hashlib.sha256(args.freeze.read_bytes()).hexdigest() or context['frozen_hashes']!=freeze['hashes']:errors.append('execution freeze differs')
windows={w['block']:w for w in freeze['public_windows']}
for name,expected in freeze['specifications'].items():
 batch=root/name;m=json.loads((batch/'manifest.json').read_text())
 spec_path=args.freeze.parent/f'{name}.json';spec=json.loads(spec_path.read_text())
 if hashlib.sha256(spec_path.read_bytes()).hexdigest()!=expected['sha256']:errors.append(name+': specification file hash changed')
 if m['spec']!=spec or digest(m['spec'])!=expected['canonical_sha256']:errors.append(name+': frozen spec mismatch')
 if m['binary_sha256']!=freeze['hashes']['build-release/tokenfs']:errors.append(name+': wrong binary')
 required_sources=['src/main.cpp','src/measured_policy.h','scripts/measured_study.py','scripts/evidence_benchmark.py']
 if m['source_hashes']!={p:freeze['hashes'][p] for p in required_sources}:errors.append(name+': wrong or missing source identity')
 if name=='measured-domain-supplement-01' and m['script_sha256']!=freeze['hashes']['scripts/measured_domain_study.py']:errors.append(name+': wrong domain runner')
 if list(batch.rglob('INVALIDATED.json')) or list(batch.rglob('failure.json')):errors.append(name+': failure/invalidation marker')
 identity=m['nvme_identity']
 if identity['transport']!='tcp' or 'traddr=28.10.10.13' not in identity['address'].split(',') or identity['subsysnqn']!='nqn.2026-09.local.aura-kv:remote-cn7':errors.append(name+': wrong remote identity')
 for b in spec['blocks']:
  case_root=batch/b['id'];trace=json.loads((case_root/'trace.json').read_text())
  if b['scenario'].startswith('mooncake_'):
   public+=1;w=windows[b['id']];src=args.trace_dir/w['source']
   if hashlib.sha256(src.read_bytes()).hexdigest()!=w['source_sha256']:errors.append(b['id']+': changed public source')
   _,regenerated,_=application(src,'confirmation',b['source_offset'],b['requests'],b['shard_mib'],b.get('paced',False))
   if trace!=regenerated or digest(trace)!=w['trace_sha256']:errors.append(b['id']+': changed public window')
  for strategy in b['variants']:
   cases+=1;p=case_root/strategy;r=json.loads((p/'result.json').read_text());rows=json.loads((p/'requests.json').read_text())
   problems=[];prev=0
   for event in rows:
    start=event['issued_s'];end=event['completed_s']
    if not all(math.isfinite(v) for v in [start,end,event['seconds']]) or not (prev<=start<=end<=r['job_wall_s']):problems.append('invalid monotonic timeline')
    # Completion includes tiny result bookkeeping after measured read latency.
    if event['seconds']<0 or event['seconds']>end-start+1e-6:problems.append('invalid read duration')
    if 'release_s' in event and start+1e-6<event['release_s']:problems.append('issued before release')
    prev=end
   if not math.isfinite(r['completed_with_background_s']) or r['completed_with_background_s']<r['job_wall_s']:problems.append('invalid background completion time')
   if problems:errors.append(f"{b['id']}/{strategy}: {sorted(set(problems))}")
 if len(list(batch.glob('*/*/result.json')))!=expected['runs']:errors.append(name+': wrong case count')
result=dict(passed=not errors,checked_performance_cases=cases,checked_public_windows=public,errors=errors)
(root/'measured-b3-independent-provenance-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2));raise SystemExit(0 if result['passed'] else 1)
