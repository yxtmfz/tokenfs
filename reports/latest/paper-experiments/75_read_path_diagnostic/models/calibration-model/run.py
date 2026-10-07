from pathlib import Path
import shutil,subprocess,json
root=Path(__file__).resolve().parent;base=root.parent/'disk-model'
shutil.copytree(base/'inputs',root/'inputs',dirs_exist_ok=True)
variants=[(h,gate,start) for h in ['retained','opportunity74'] for gate in ['old','copy_calibrated','all_calibrated'] for start in ['warm','cold']]
for h,gate,start in variants:
 name=f'{h}_{gate}_{start}';d=root/name;d.mkdir(exist_ok=True)
 s=(base/h/'measured_policy.h').read_text()
 if gate!='old':
  old='if(o.adaptive_control && !needed && (o.bounded_cost_warmup'
  new='if(o.adaptive_control && !needed && '+('!copy_.n' if gate=='copy_calibrated' else '!(copy_.n && local_.n && remote_.n)')+' && (o.bounded_cost_warmup'
  assert old in s;s=s.replace(old,new)
 # Expose only a diagnostic state summary, no new control.
 s=s.replace('  bool Observe(','''  std::string CalibrationStats() const {
    std::lock_guard<std::mutex> lock(mu_);
    return " remote_samples="+std::to_string(remote_.n)+" local_samples="+std::to_string(local_.n)+" copy_samples="+std::to_string(copy_.n);
  }
  bool Observe(''',1)
 (d/'measured_policy.h').write_text(s);(d/'run_reuse.h').write_bytes((base/h/'run_reuse.h').read_bytes())
 r=(base/h/'replay.cpp').read_text()
 if start=='cold':
  r=r.replace('policy.ReadSample(false,size,21000);policy.ReadSample(true,size,10500);policy.CopySample(size,8000);','')
  r=r.replace('   if(captured||local)continue;', '   if(!captured)policy.ReadSample(local,size,local?10500:21000,o.bounded_cost_warmup);\n   if(captured||local)continue;')
  r=r.replace('caches[selected][key]=i;++copies;', 'caches[selected][key]=i;policy.CopySample(size,8000,o.bounded_cost_warmup);++copies;')
 r=r.replace('i=0,remote=0,copies=0;', 'i=0,remote=0,copies=0,ramhits=0,diskhits=0,headroom_copies=0;')
 r=r.replace('   ram.remove(key);','   if(captured)++ramhits;else if(local)++diskhits;\n   ram.remove(key);')
 r=r.replace('if(selected>=0){for(auto&v:chosen.victims)', 'if(selected>=0){headroom_copies+=chosen.explore_headroom;for(auto&v:chosen.victims)')
 r=r.replace('<<" copies="<<copies;', '<<" copies="<<copies<<" ram_hits="<<ramhits<<" disk_hits="<<diskhits<<" requests="<<i<<" headroom_copies="<<headroom_copies;')
 r=r.replace('std::cout<<"\\n";', 'std::cout<<policy.CalibrationStats()<<"\\n";')
 (d/'replay.cpp').write_text(r)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
old=json.loads((base/'results.json').read_text());rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 for h,gate,start in variants:
  name=f'{h}_{gate}_{start}'
  result=subprocess.run([str(root/name/'replay'),str(p),'prior'],capture_output=True,text=True,check=True)
  arms={}
  for line in result.stdout.splitlines():
   cells=line.split();arms[cells[0]]={k:int(v) for k,v in [cell.split('=') for cell in cells[1:]]}
  for a in arms.values():
   assert a['remote']+a['ram_hits']+a['disk_hits']==a['requests']==1152
   if start=='cold':assert a['remote_samples']==a['remote'] and a['local_samples']==a['disk_hits'] and a['copy_samples']==a['copies']
   else:assert a['remote_samples']==a['local_samples']==a['copy_samples']==1
  if gate=='old' and start=='warm':
   orig=next(r for r in old['rows'] if r['input']==p.stem)['variants'][h]['arms']
   for a,m in orig.items():assert {k:arms[a][k] for k in m}==m
  row['variants'][name]={'stdout':result.stdout,'arms':arms}
 rows.append(row)
result={'speed_evidence':False,'description':'Fixed 10 inputs × 2 H algorithms × 3 shared headroom calibration gates × 2 starts × 4 arms = 480 model arms. Warm start initializes all fixed samples. Cold start initializes none, samples every actual disk/remote read (21/10.5 ms) and every copy (8 ms). No RAM sample. Gates shared by Full/NoH/NoP/NoJ; both original and new controls retained. Constant costs, instantaneous copies; not throughput/p99 evidence.','rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Headroom calibration eligibility model','',result['description'],'','Cells: remote / local disk / copies / free-headroom copies. RAM hits identical across this matrix for each input.','', '| Input | Variant | Full | NoH | NoP | NoJ |','|---|---|---:|---:|---:|---:|']
for row in rows:
 for name,d in row['variants'].items():
  arms=d['arms'];cells=[' / '.join(str(arms[a][k]) for k in ['remote','disk_hits','copies','headroom_copies']) for a in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+row['input']+' | '+name+' | '+' | '.join(cells)+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
