from pathlib import Path
import subprocess,json
root=Path(__file__).resolve().parent
variants=['disk_clock_persistent_raw','disk_clock_persistent_matched','logical_clock_persistent_raw','logical_clock_persistent_matched']
for variant in variants:
 d=root/variant;d.mkdir(exist_ok=True)
 parent=root/variant.replace('_persistent','')
 for name in ['replay.cpp','run_reuse.h']:(d/name).write_bytes((parent/name).read_bytes())
 s=(parent/'measured_policy.h').read_text()
 observe='''        auto& entry=disk_long_[key];
        if(entry.last) {
          const double gap=DiskClock()-entry.last;
          entry.n=std::min<uint64_t>(entry.n+1,std::max<size_t>(2,o.window));
          const double alpha=1.0/entry.n,delta=gap-entry.mean;
          entry.mean+=alpha*delta;
          entry.variance=(1-alpha)*(entry.variance+alpha*delta*delta);
        }
        entry.last=DiskClock();entry.generation=++disk_generation_;
        disk_long_events_.push_back({key,entry.generation});
        while(disk_long_events_.size()>std::max<size_t>(2,o.window)) {
          const auto old=disk_long_events_.front();disk_long_events_.pop_front();
          auto found=disk_long_.find(old.first);
          if(found!=disk_long_.end() && found->second.generation==old.second)disk_long_.erase(found);
        }
'''
 s=s.replace('        ++disk_observations_;','        ++disk_observations_;\n'+observe)
 s=s.replace('  double DiskDemand(const std::string& key,const Options& o) const {', '''  double LongDiskDemand(const std::string& key,const Options& o) const {
    const auto found=disk_long_.find(key);if(found==disk_long_.end())return 0;
    const auto& e=found->second;if(!e.n)return 0;
    const double gap=std::max(1.0,e.mean);
    const double grace=gap+std::sqrt(std::max(0.0,e.variance));
    const double overdue=std::max(0.0,double(DiskClock()-e.last)-grace);
    return double(o.window)/gap*double(e.n)/(e.n+1.0)*std::exp2(-overdue/gap);
  }
  double ShortDiskDemand(const std::string& key,const Options& o) const {''')
 s=s.replace('  double NoiseScale(','''  double DiskDemand(const std::string& key,const Options& o) const {
    return std::max(ShortDiskDemand(key,o),LongDiskDemand(key,o));
  }
  double NoiseScale(''')
 # Matching noise transformation is retained unmodified to isolate the persistent forecast.
 s=s.replace('  uint64_t observations_=0,disk_observations_=0;', '''  struct DiskMoment { uint64_t n=0,last=0,generation=0;double mean=0,variance=0; };
  std::unordered_map<std::string,DiskMoment> disk_long_;
  std::deque<std::pair<std::string,uint64_t>> disk_long_events_;
  uint64_t disk_generation_=0;
  uint64_t observations_=0,disk_observations_=0;''')
 (d/'measured_policy.h').write_text(s)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
base=json.loads((root/'results.json').read_text());rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 original=next(r for r in base['rows'] if r['input']==p.stem)
 for variant in variants:
  result=subprocess.run([str(root/variant/'replay'),str(p),'prior'],capture_output=True,text=True,check=True)
  arms={}
  for line in result.stdout.splitlines():
   cells=line.split();arms[cells[0]]={k:int(v) for k,v in [cell.split('=') for cell in cells[1:]]}
  assert arms['NoHotspot']==original['variants']['retained']['arms']['NoHotspot'],(p,variant)
  row['variants'][variant]={'stdout':result.stdout,'arms':arms}
 rows.append(row)
result={'speed_evidence':False,'description':'Persistent actual non-RAM demand; per-key all disk request gaps observed (including cache hits), bounded last 128 disk-event generations, recency expiry after mean+std; no future access. Same 10 inputs and four arms.','variants':variants,'rows':rows}
(root/'persistent-results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Persistent disk demand model','',result['description'],'','NoHotspot equality against retained policy checked for all 40 controls.','', '| Input | Variant | Full remote/copies | NoH remote/copies | NoP remote/copies | NoJ remote/copies |','|---|---|---:|---:|---:|---:|']
for row in rows:
 for variant in variants:
  arms=row['variants'][variant]['arms'];cells=[f"{arms[a]['remote']}/{arms[a]['copies']}" for a in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+row['input']+' | '+variant+' | '+' | '.join(cells)+' |')
(root/'persistent-tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
