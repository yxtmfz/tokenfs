from pathlib import Path
import subprocess,shutil,json,hashlib
root=Path(__file__).resolve().parent
prior=root.parent/'disk-model'
shutil.copytree(prior/'inputs',root/'inputs',dirs_exist_ok=True)
variants=['retained','cohort_beta_outcome','cohort_hit_outcome']
base=(prior/'retained/measured_policy.h').read_text()
reuse=(prior/'retained/run_reuse.h').read_text()
replay=(prior/'retained/replay.cpp').read_text()
public='''  // Only realized storage hits are outcomes. A copy enters this table when
  // installed; its eventual eviction closes its fully observed residence.
  // Remaining copies at end of replay are right-censored, never failure zeros.
  void CopyInstalled(int location,const std::string& key,const Options& o) {
    std::lock_guard<std::mutex> lock(mu_);
    if(o.static_reuse_value)return;
    const auto identity=std::make_pair(location,key);
    if(copy_outcomes_.count(identity))throw std::runtime_error("copy installed twice without retirement");
    copy_outcomes_[identity]={!run_reuse_.HasCompletedReturn(key),0};
    ++outcome_installed_;if(copy_outcomes_.at(identity).newcomer)++outcome_newcomers_;
  }
  void CopyDiskHit(int location,const std::string& key,const Options& o) {
    std::lock_guard<std::mutex> lock(mu_);
    if(o.static_reuse_value)return;
    const auto found=copy_outcomes_.find({location,key});
    if(found!=copy_outcomes_.end())++found->second.hits;
  }
  void CopyEvicted(int location,const std::string& key,const Options& o) {
    std::lock_guard<std::mutex> lock(mu_);
    if(o.static_reuse_value)return;
    const auto found=copy_outcomes_.find({location,key});
    if(found==copy_outcomes_.end())throw std::runtime_error("retired unobserved copy");
    ++outcome_closed_all_;
    // Train newcomer prior only on copies admitted before a distinct return.
    // Repeated hot copies must not confer their success on unseen newcomers.
    if(found->second.newcomer) {
      const uint64_t hits=found->second.hits;
      closed_newcomer_outcomes_.push_back(hits);closed_hit_sum_+=hits;closed_success_sum_+=hits>0;
      ++outcome_closed_newcomers_;outcome_successes_+=hits>0;outcome_hits_+=hits;
      while(closed_newcomer_outcomes_.size()>std::max<size_t>(2,o.window)) {
        closed_hit_sum_-=closed_newcomer_outcomes_.front();closed_success_sum_-=closed_newcomer_outcomes_.front()>0;
        closed_newcomer_outcomes_.pop_front();
      }
    }
    copy_outcomes_.erase(found);
  }
  std::string OutcomeStats() const {
    std::lock_guard<std::mutex> lock(mu_);
    size_t censored=0;for(const auto& p:copy_outcomes_)censored+=p.second.newcomer;
    return " installed="+std::to_string(outcome_installed_)+" newcopies="+std::to_string(outcome_newcomers_)+
      " closed_all="+std::to_string(outcome_closed_all_)+" closed_new="+std::to_string(outcome_closed_newcomers_)+
      " closed_success="+std::to_string(outcome_successes_)+" closed_hits="+std::to_string(outcome_hits_)+
      " censored_new="+std::to_string(censored)+" calibration_count="+std::to_string(closed_newcomer_outcomes_.size());
  }
'''
private='''  double OutcomeDiscount() const {
    return std::min(1.0,double(NUMERATOR+1)/(closed_newcomer_outcomes_.size()+2.0));
  }
  struct CopyOutcome {bool newcomer=false;uint64_t hits=0;};
  std::map<std::pair<int,std::string>,CopyOutcome> copy_outcomes_;
  std::deque<uint64_t> closed_newcomer_outcomes_;
  uint64_t closed_hit_sum_=0,closed_success_sum_=0;
  uint64_t outcome_installed_=0,outcome_newcomers_=0,outcome_closed_all_=0,outcome_closed_newcomers_=0,outcome_successes_=0,outcome_hits_=0;
'''
for variant in variants:
 d=root/variant;d.mkdir(exist_ok=True)
 s=base;u=reuse;r=replay
 if variant!='retained':
  s=s.replace('#include <mutex>','#include <mutex>\n#include <map>\n#include <stdexcept>')
  s=s.replace('  bool Observe(',public+'  bool Observe(',1)
  s=s.replace('    (void)gpu;return temporal_strength_*run_reuse_.NewcomerDiskPrior(key)*run_reuse_.NewcomerSurvival(key,observations_);','    (void)gpu;return OutcomeDiscount()*temporal_strength_*run_reuse_.NewcomerDiskPrior(key)*run_reuse_.NewcomerSurvival(key,observations_);')
  s=s.replace('  mutable std::mutex mu_;',private.replace('NUMERATOR','closed_success_sum_' if variant=='cohort_beta_outcome' else 'closed_hit_sum_')+'  mutable std::mutex mu_;')
  u=u.replace('  size_t Entries() const', '  bool HasCompletedReturn(const std::string& key) const {\n    const auto found=entries_.find(key);return found!=entries_.end() && found->second.gap.n>0;\n  }\n  size_t Entries() const')
  r=r.replace('++i;bool local=false;','++i;bool local=false;int location=-1;')
  r=r.replace('{local=true;c[key]=i;}','{local=true;location=g;c[key]=i;}')
  r=r.replace('policy.Observe(caller,key,o,local||captured);','policy.Observe(caller,key,o,local||captured);\n   if(local && !captured)policy.CopyDiskHit(location,key,o);')
  r=r.replace('caches[selected].erase(v);','policy.CopyEvicted(selected,v,o);caches[selected].erase(v);')
  r=r.replace('caches[selected][key]=i;++copies;','caches[selected][key]=i;policy.CopyInstalled(selected,key,o);++copies;')
  r=r.replace('std::cout<<"\\n";', 'std::cout<<policy.OutcomeStats()<<"\\n";')
 (d/'measured_policy.h').write_text(s);(d/'run_reuse.h').write_text(u);(d/'replay.cpp').write_text(r)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
rows=[]
for p in sorted((root/'inputs').glob('*.txt')):
 row={'input':p.stem,'variants':{}}
 for variant in variants:
  result=subprocess.run([str(root/variant/'replay'),str(p),'prior'],capture_output=True,text=True,check=True)
  arms={}
  for line in result.stdout.splitlines():
   cells=line.split();arms[cells[0]]={k:int(v) for k,v in [cell.split('=') for cell in cells[1:]]}
  row['variants'][variant]={'stdout':result.stdout,'arms':arms}
  if variant!='retained':
   baseline=row['variants']['retained']['arms']['NoHotspot'];candidate=arms['NoHotspot']
   assert {k:candidate[k] for k in baseline}==baseline
   assert all(candidate[k]==0 for k in set(candidate)-set(baseline))
 rows.append(row)
result={'speed_evidence':False,'description':'Fixed 10 known inputs × 3 versions × 4 arms. Only completed newcomer copy residencies train discount; real disk hits exclude RAM. End residents right-censored. Beta(1,1) success or hit-count discount multiplies original cohort prior. Constant costs and immediate copies, not actual throughput/p99.','rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Realized newcomer outcome calibration','',result['description'],'','| Input | Variant | Full remote/copies | NoH remote/copies | NoP remote/copies | NoJ remote/copies | Full closed-new/success/hits/censored |','|---|---|---:|---:|---:|---:|---:|']
for row in rows:
 for variant in variants:
  arms=row['variants'][variant]['arms'];cells=[f"{arms[a]['remote']}/{arms[a]['copies']}" for a in ['Full','NoHotspot','NoAffinity','NoJoint']];f=arms['Full']
  outcome='/'.join(str(f[k]) for k in ['closed_new','closed_success','closed_hits','censored_new']) if variant!='retained' else 'unrecorded'
  lines.append('| '+row['input']+' | '+variant+' | '+' | '.join(cells)+' | '+outcome+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
