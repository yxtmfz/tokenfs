from pathlib import Path
import shutil
root=Path(__file__).resolve().parent
src=root.parents[1]/'hotspot-object77/capacity-boundary'
shutil.copytree(src/'inputs',root/'inputs',dirs_exist_ok=True)
for name in ['measured_policy.h','run_reuse.h']:shutil.copy(src/'native'/name,root/name)
f=root/'run_reuse.h';s=f.read_text();s=s.replace('namespace tokenfs_policy {','namespace tokenfs_policy {\ninline bool diagnostic_conditional_prior=false;')
s=s.replace('if(active_length_)entries_.at(active_).length.Add(active_length_,limit);','if(active_length_) {auto& previous=entries_.at(active_);if(!previous.first_length)previous.first_length=active_length_;previous.length.Add(active_length_,limit);}')
s=s.replace('if(object_weighted)return double(recurrent_entries_)/(entries_.size()+1.0);','''if(object_weighted) {
      if(diagnostic_conditional_prior && key==active_ && active_length_>1) {
        size_t evidence=0,returned=0;
        for(const auto& [peer,p]:entries_)if(peer!=key && p.first_length>=active_length_) {
          ++evidence;if(p.gap.n)++returned;
        }
        return double(returned)/(evidence+1.0);
      }
      return double(recurrent_entries_)/(entries_.size()+1.0);
    }''')
s=s.replace('uint64_t last_start=0,last_seen=0,generation=0,novelty_seen=0;','uint64_t first_length=0,last_start=0,last_seen=0,generation=0,novelty_seen=0;')
f.write_text(s)
f=root/'measured_policy.h';s=f.read_text().replace('namespace tokenfs_policy {','namespace tokenfs_policy {\ninline bool diagnostic_cost_bootstrap=false;')
s=s.replace('if(o.adaptive_control && !needed && (o.bounded_cost_warmup', 'if(o.adaptive_control && !needed && (!diagnostic_cost_bootstrap || !result.costs_calibrated) && (o.bounded_cost_warmup')
f.write_text(s)
f=root/'run_reuse.h';s=f.read_text().replace('inline bool diagnostic_conditional_prior=false;', '''inline bool diagnostic_conditional_prior=false;
inline bool diagnostic_censored_cohort=false;
inline bool diagnostic_ram_hit=false;''')
s=s.replace('limit=std::max<size_t>(2,limit);','''limit=std::max<size_t>(2,limit);
    // Every label spans the full observed request horizon. No unfinished
    // target contributes a training outcome, and RAM-served returns add zero.
    while(!cohort_pending_.empty() && at-cohort_pending_.front().start>=limit) {
      const auto old=cohort_pending_.front();cohort_pending_.pop_front();
      cohort_return_sum_+=old.returns;cohort_completed_.push_back(old.returns);
      while(cohort_completed_.size()>limit){cohort_return_sum_-=cohort_completed_.front();cohort_completed_.pop_front();}
    }
    if(!entries_.count(key))cohort_pending_.push_back({key,at,0});
    else if(key!=active_ && !diagnostic_ram_hit) {
      for(auto& pending:cohort_pending_)if(pending.key==key){++pending.returns;break;}
    }''',1)
s=s.replace('// Each retained object supplies at most one piece of return evidence.', '''if(diagnostic_censored_cohort)
      return double(cohort_return_sum_)/(cohort_completed_.size()+1.0);
    // Each retained object supplies at most one piece of return evidence.''')
s=s.replace('struct Moment {','''struct CohortPending {std::string key;uint64_t start,returns;};
  std::deque<CohortPending> cohort_pending_;
  std::deque<uint64_t> cohort_completed_;
  uint64_t cohort_return_sum_=0;
  struct Moment {''')
f.write_text(s)
