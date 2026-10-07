from pathlib import Path
import shutil,subprocess,json,hashlib
root=Path(__file__).resolve().parent
workspace=root.parents[2]
src=workspace/'work/tokenfs-eval/src'
old=workspace/'work/hotspot-opportunity-screen'
shutil.copytree(old/'inputs',root/'inputs',dirs_exist_ok=True)
base=(src/'measured_policy.h').read_text()
replay=(old/'source-replay.cpp').read_text()
variants=['retained','opportunity74','disk_clock_raw','disk_clock_matched','logical_clock_raw','logical_clock_matched']
method='''  bool DiskDemandEnabled(const Options& o) const {
    return !o.static_reuse_value && o.retained_capture && o.causal_window && o.shared_value;
  }
  uint64_t DiskClock() const {return CLOCK;}
  double DiskSurvival(const std::string& key,const Options& o) const {
    if(!o.shift_reset)return 1.0;
    const auto found=disk_positions_.find(key);
    if(found==disk_positions_.end() || found->second.size()<2)return 1.0;
    const auto& p=found->second;
    const double gap=double(p.back()-p.front())/(p.size()-1);
    return std::exp2(-(o.adaptive_control?temporal_strength_:1.0)*double(DiskClock()-p.back())/std::max(4.0,gap));
  }
  double DiskDemand(const std::string& key,const Options& o) const {
    const auto found=disk_positions_.find(key);if(found==disk_positions_.end())return 0;
    const double n=found->second.size();
    return (o.frequency_admission?n:std::max(0.0,n-1.0))*DiskSurvival(key,o);
  }
  double NoiseScale(int gpu,const std::string& key,const Options& o,bool incoming) const {
    if(MATCHED && DiskDemandEnabled(o)) {
      const auto found=disk_positions_.find(key);
      return found==disk_positions_.end()?0:std::sqrt(double(found->second.size()))*DiskSurvival(key,o);
    }
    return std::sqrt(double(EffectiveCount(gpu,key,o,incoming)));
  }
'''
observe='''    // Record only actual requests reaching disk/remote storage. Disk hits count
    // as demand too, so admission does not censor future frequency observations.
    // RAM requests add no event; logical-clock expiry still tracks elapsed time.
    if(DiskDemandEnabled(o)) {
      if(disk_access) {
        ++disk_observations_;
        disk_history_.push_back({key,DiskClock()});
        disk_positions_[key].push_back(DiskClock());
      }
      while(!disk_history_.empty() && DiskClock()-disk_history_.front().second>=std::max<size_t>(2,o.window)) {
        auto found=disk_positions_.find(disk_history_.front().first);
        found->second.pop_front();if(found->second.empty())disk_positions_.erase(found);
        disk_history_.pop_front();
      }
    }
'''
for variant in variants:
 d=root/variant;d.mkdir(exist_ok=True)
 shutil.copy2(src/'run_reuse.h',d/'run_reuse.h')
 s=base;r=replay
 if variant=='retained':r=r.replace('o.disk_opportunity_value=true;','o.disk_opportunity_value=false;')
 if 'clock_' in variant:
  s=s.replace('bool* affinity_reset=nullptr)', 'bool* affinity_reset=nullptr,bool disk_access=true)')
  s=s.replace('    ++observations_;','    ++observations_;\n'+observe,1)
  s=s.replace('  bool DiskOpportunityEnabled(',method.replace('CLOCK','disk_observations_' if variant.startswith('disk_') else 'observations_').replace('MATCHED','true' if variant.endswith('_matched') else 'false')+'  bool DiskOpportunityEnabled(',1)
  s=s.replace('  double PersistentEstimate(const std::string& key,const Options& o) const {','  double PersistentEstimate(const std::string& key,const Options& o) const {\n    if(DiskDemandEnabled(o))return DiskDemand(key,o);')
  s=s.replace('  double CohortDiskReuse(int gpu,const std::string& key,const Options& o) const {','  double CohortDiskReuse(int gpu,const std::string& key,const Options& o) const {\n    if(DiskDemandEnabled(o))return 0;')
  s=s.replace('    if(DiskOpportunityEnabled(o)) {\n      const double recent=', '    if(DiskDemandEnabled(o))return DiskDemand(item.key,o)*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;\n    if(DiskOpportunityEnabled(o)) {\n      const double recent=')
  s=s.replace('std::sqrt(double(EffectiveCount(gpu,victim.key,o,false)))','NoiseScale(gpu,victim.key,o,false)')
  s=s.replace('std::sqrt(double(result.affinity_incoming_count))','NoiseScale(gpu,incoming.key,o,true)')
  s=s.replace('  uint64_t observations_=0;','  uint64_t observations_=0,disk_observations_=0;\n  std::deque<std::pair<std::string,uint64_t>> disk_history_;\n  std::unordered_map<std::string,std::deque<uint64_t>> disk_positions_;')
  r=r.replace('policy.Observe(caller,key,o,local||captured);','policy.Observe(caller,key,o,local||captured,nullptr,!captured);')
 (d/'measured_policy.h').write_text(s);(d/'replay.cpp').write_text(r)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 for variant in variants:
  result=subprocess.run([str(root/variant/'replay'),str(p),'prior'],capture_output=True,text=True,check=True)
  lines=result.stdout.splitlines();parsed={}
  for line in lines:
   cells=line.split();parsed[cells[0]]={k:int(v) for k,v in [cell.split('=') for cell in cells[1:]]}
  row['variants'][variant]={'stdout':result.stdout,'arms':parsed}
 for variant in variants:
  assert row['variants'][variant]['arms']['NoHotspot']==row['variants']['retained']['arms']['NoHotspot'],(p,variant)
 rows.append(row)
result={'speed_evidence':False,'description':'Fixed 10 known inputs; four arms per variant. Constant remote/local/copy costs; instantaneous copies. Not throughput or latency evidence.','variants':variants,'rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Disk demand model screening','',result['description'],'','NoHotspot equality against unmodified retained policy checked for all variants and inputs.','', '| Input | Variant | Full remote/copies | NoH remote/copies | NoP remote/copies | NoJ remote/copies |','|---|---|---:|---:|---:|---:|']
for row in rows:
 for variant in variants:
  arms=row['variants'][variant]['arms'];cells=[f"{arms[a]['remote']}/{arms[a]['copies']}" for a in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+row['input']+' | '+variant+' | '+' | '.join(cells)+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n')
print('\n'.join(lines))
