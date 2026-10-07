from pathlib import Path
import subprocess,json,shutil
root=Path(__file__).resolve().parent
repo=root.parents[2]/'tokenfs-eval'
# All models are development mechanism screens, not measured speeds.
repo=Path('/Users/mafuze/Documents/Codex/2026-09-18/new-chat/work/tokenfs-eval')
src=repo/'src';models=repo/'reports/latest/paper-experiments/74_disk_opportunity/models'
variants=['baseline74','ram_replan','disk_novelty','admission_novelty','ram_admission_novelty','lease_value','lease_ram']
for v in variants:
 d=root/v;d.mkdir(exist_ok=True)
 h=(src/'measured_policy.h').read_text();rr=(src/'run_reuse.h').read_text();r=(models/'source-replay.cpp').read_text()
 # New access capability is observed tier, never future input.
 h=h.replace('bool* affinity_reset=nullptr)', 'bool* affinity_reset=nullptr,bool disk_access=true)')
 h=h.replace('run_reuse_.Observe(key,observations_,o.window);','run_reuse_.Observe(key,observations_,o.window,disk_access);')
 rr=rr.replace('uint64_t at,size_t limit) {','uint64_t at,size_t limit,bool disk_access=true) {',1)
 rr=rr.replace('    limit=std::max<size_t>(2,limit);','    limit=std::max<size_t>(2,limit);\n    (void)disk_access;',1)
 h=h.replace('  size_t Entries() const {','''  bool ReplanMature(const std::string& key,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);
    return !o.static_reuse_value && run_reuse_.HasReturn(key);
  }
  void Admitted(const std::string& key,const Options& o) {
    std::lock_guard<std::mutex> lock(mu_);
    if(!o.static_reuse_value)run_reuse_.Admitted(key,observations_);
  }
  size_t Entries() const {''',1)
 rr=rr.replace('  size_t Entries() const {','''  bool HasReturn(const std::string& key) const {
    auto it=entries_.find(key);return it!=entries_.end() && it->second.gap.n>0;
  }
  void Admitted(const std::string& key,uint64_t at) {
    auto it=entries_.find(key);if(it==entries_.end())return;
    ADMISSION_UPDATE
    it->second.admitted_at=at;
    it->second.admitted_value=DiskOpportunity(key,at,128);
  }
  double Lease(const std::string& key,uint64_t at) const {
    auto it=entries_.find(key);if(it==entries_.end())return 0;
    const auto& e=it->second;
    return e.admitted_at && e.gap.n && at-e.admitted_at<=e.gap.mean?e.admitted_value:0;
  }
  size_t Entries() const {''',1)
 rr=rr.replace('uint64_t last_start=0,last_seen=0,generation=0,novelty_seen=0;', 'uint64_t last_start=0,last_seen=0,generation=0,novelty_seen=0,disk_seen=0,admitted_at=0;double admitted_value=0;bool was_admitted=false;')
 rr=rr.replace('ADMISSION_UPDATE','if(!it->second.was_admitted){++novelty_;it->second.was_admitted=true;} it->second.novelty_seen=novelty_;' if 'admission_novelty' in v else '')
 if v=='disk_novelty':
  rr=rr.replace('    (void)disk_access;','    if(disk_access && entries_[key].disk_seen++==1)++novelty_;')
  rr=rr.replace('if(!entry.gap.n)++novelty_;','')
 if 'admission_novelty' in v:rr=rr.replace('if(!entry.gap.n)++novelty_;','')
 if v.startswith('lease_'):
  h=h.replace('const double repeats=std::max(recent,opportunity*competition);','const double repeats=std::max({recent,opportunity*competition,run_reuse_.Lease(item.key,observations_)});')
 r=r.replace('policy.Observe(caller,key,o,local||captured);','policy.Observe(caller,key,o,local||captured,nullptr,!captured);')
 r=r.replace('if(captured||local)continue;++remote;','if(!captured && !local)++remote;\n   if(local || (captured && !(RAM_REPLAN && policy.ReplanMature(key,o))))continue;')
 r=r.replace('RAM_REPLAN','true' if 'ram' in v else 'false')
 r=r.replace('caches[selected][key]=i;++copies;','caches[selected][key]=i;policy.Admitted(key,o);++copies;')
 (d/'measured_policy.h').write_text(h);(d/'run_reuse.h').write_text(rr);(d/'replay.cpp').write_text(r)
 subprocess.run(['c++','-std=c++17','-O2','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
rows=[]
for p in sorted((models/'inputs').glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 for v in variants:
  raw=subprocess.run([str(root/v/'replay'),str(p),'prior'],capture_output=True,text=True,check=True).stdout
  arms={}
  for l in raw.splitlines():
   cells=l.split();arms[cells[0]]={k:int(val) for k,val in [c.split('=') for c in cells[1:]]}
  row['variants'][v]={'stdout':raw,'arms':arms}
  assert arms['NoHotspot']==row['variants']['baseline74']['arms']['NoHotspot'],(p,v)
 rows.append(row)
result={'speed_evidence':False,'description':'Fixed known 10 inputs, 7 mechanisms, 4 arms. Instant copies, 21ms remote /10.5ms local /8ms copy. Model has no real scheduling overhead, RAM lease or asynchronous write pressure; not measured speeds or p99. Every NoHotspot arm identical.','variants':variants,'rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Feedback mechanism screening','',result['description'],'','|Input|Variant|Full remote/copies|NoH|NoP|NoJ|','|---|---|---:|---:|---:|---:|']
for row in rows:
 for v in variants:
  a=row['variants'][v]['arms'];lines.append('|'+row['input']+'|'+v+'|'+'|'.join(str(a[k]['remote'])+'/'+str(a[k]['copies']) for k in ['Full','NoHotspot','NoAffinity','NoJoint'])+'|')
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
