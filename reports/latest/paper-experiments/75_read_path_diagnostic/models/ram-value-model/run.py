from pathlib import Path
import subprocess,shutil,json,hashlib
root=Path(__file__).resolve().parent
base=root.parent/'disk-model'
shutil.copytree(base/'inputs',root/'inputs',dirs_exist_ok=True)
variants=[(policy,ram) for policy in ['retained','opportunity74'] for ram in ['lru','disk_value','ram_value']]
for policy,ram in variants:
 name=policy+'_'+ram;d=root/name;d.mkdir(exist_ok=True)
 for f in ['measured_policy.h','run_reuse.h']:(d/f).write_bytes((base/policy/f).read_bytes())
 s=(base/policy/'replay.cpp').read_text()
 s=s.replace('std::list<std::string> ram;', 'std::list<std::string> ram;std::map<std::string,uint64_t> ram_recency;')
 s=s.replace('i=0,remote=0,copies=0;', 'i=0,remote=0,copies=0,ramhits=0,diskhits=0;')
 old='ram.remove(key);ram.push_back(key);if(ram.size()>2)ram.pop_front();'
 assert old in s
 new='''if(captured)++ramhits;else if(local)++diskhits;
   ram.remove(key);ram.push_back(key);ram_recency[key]=i;
   if(ram.size()>2) {
     VICTIM_CODE
   }'''
 if ram=='lru':victim='const auto victim=ram.front();ram.pop_front();ram_recency.erase(victim);'
 else:
  victim='''// Only the previous two retained objects compete; the newly read
     // object must still be captured. Budget stays exactly two 2-MiB objects.
     Options ro=o;RAM_OPTION
     std::vector<Item> choices;
     for(const auto& k:ram)if(k!=key)choices.push_back({k,size,ram_recency.at(k),1.0});
     auto ranked=policy.Ranked(caller,std::move(choices),ro);
     if(ranked.size()!=2)throw std::runtime_error("RAM victim set mismatch");
     const auto victim=ranked.front().key;ram.remove(victim);ram_recency.erase(victim);'''.replace('RAM_OPTION','ro.retained_capture=false;' if ram=='ram_value' else '')
 s=s.replace(old,new.replace('VICTIM_CODE',victim))
 s=s.replace('   if(captured||local)continue;', '   if(ram.size()>2 || ram_recency.size()!=ram.size() || std::find(ram.begin(),ram.end(),key)==ram.end())throw std::runtime_error("RAM budget/current-capture invariant");\n   if(captured||local)continue;')
 s=s.replace('<<" copies="<<copies;', '<<" copies="<<copies<<" ram_hits="<<ramhits<<" disk_hits="<<diskhits<<" requests="<<i;')
 (d/'replay.cpp').write_text(s)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
original=json.loads((base/'results.json').read_text());rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 for policy,ram in variants:
  name=policy+'_'+ram
  result=subprocess.run([str(root/name/'replay'),str(p),'prior'],capture_output=True,text=True,check=True)
  arms={}
  for line in result.stdout.splitlines():
   cells=line.split();arms[cells[0]]={k:int(v) for k,v in [cell.split('=') for cell in cells[1:]]}
  for a in arms.values():assert a['remote']+a['disk_hits']+a['ram_hits']==a['requests']
  if ram=='lru':
   previous=next(r for r in original['rows'] if r['input']==p.stem)['variants'][policy]['arms']
   for a,metrics in previous.items():assert {k:arms[a][k] for k in metrics}==metrics
  row['variants'][name]={'stdout':result.stdout,'arms':arms}
 rows.append(row)
result={'speed_evidence':False,'module_extension':True,'description':'Fixed 10 inputs × 2 H algorithms × 3 RAM replacement choices × 4 arms = 240 model arms. LRU baseline vs original disk-value ranking vs retained_capture=false RAM-value ranking. RAM always captures incoming storage read; chooses victim only among previous 2 objects; exact 4MiB budget. All compared arms use same victim-selection code with existing H/P/J flags. No physical pinning/concurrency in serialized immediate-copy model; no throughput/p99 evidence. This extends H to RAM placement, not unchanged original H.','rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Cross-tier RAM victim ranking model','',result['description'],'','Each cell: remote reads / local disk hits / RAM hits / copies.','', '| Input | Variant | Full | NoH | NoP | NoJ |','|---|---|---:|---:|---:|---:|']
for row in rows:
 for name,data in row['variants'].items():
  arms=data['arms'];cells=[' / '.join(str(arms[a][k]) for k in ['remote','disk_hits','ram_hits','copies']) for a in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+row['input']+' | '+name+' | '+' | '.join(cells)+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
