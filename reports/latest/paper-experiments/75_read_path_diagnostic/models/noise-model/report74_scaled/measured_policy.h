#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include "run_reuse.h"

namespace tokenfs_policy {
// Recent reuse is an estimate, not future knowledge. Each domain sees only accesses
// observed so far. Rates include measured foreground I/O and verified-copy time.
struct Item { std::string key; uint64_t bytes=0; uint64_t recency=0; double coverage=1.0; };
struct Options {
  size_t window=128;
  bool aging=true;
  bool admission=true;
  bool cost=true;
  bool value_victim=true;
  bool size_aware=true;
  bool frequency_admission=false;
  bool shift_reset=false;
  size_t shift_window=8;
  bool track_affinity=false;
  bool affinity_gate=false;
  bool joint_admission=true;
  size_t affinity_window=128;
  bool affinity_recent_demand=false;
  bool affinity_handover_epoch=false;
  bool shared_value=false;
  bool causal_window=false;
  bool burst_reuse=false;
  bool adaptive_control=false;
  bool efficient_planning=false;
  bool burst_interval_survival=false;
  bool reuse_scaled_exploration=false;
  bool persistent_run_reuse=false;
  bool persistent_reuse_immediate_decay=false;
  bool static_reuse_value=false;
  bool novel_reuse_decay=false;
  bool retained_capture=false;
  bool bounded_cost_warmup=false;
  bool cohort_reuse_prior=false;
  bool recent_value_floor=false;
  bool disk_opportunity_value=false;
};
struct Decision {
  bool allowed=false;
  std::string reason;
  double incoming_us=0, displaced_us=0, copy_us=0;
  bool costs_calibrated=false;
  double burst_remaining=0;
  double uncertainty_us=0;
  bool explore_headroom=false;
  double exploration_reads=1;
  double cohort_disk_reuse=0;
  uint64_t incoming_count=0;
  uint64_t affinity_incoming_count=0;
  uint64_t affinity_adjusted_items=0;
  uint64_t survival_adjusted_items=0;
  uint64_t persistent_reuse_adjusted_items=0;
  std::vector<std::string> victims;
};

class MeasuredPolicy {
 public:
  bool Observe(int gpu,const std::string& key,const Options& o,bool local_hit=false,bool* affinity_reset=nullptr) {
    std::lock_guard<std::mutex> lock(mu_);
    if(affinity_reset)*affinity_reset=false;
    ++observations_;
    if(o.persistent_run_reuse && o.causal_window && o.shared_value && o.burst_reuse)
      run_reuse_.Observe(key,observations_,o.window);
    if(o.burst_reuse) {
      if(active_burst_key_==key)++active_burst_length_;
      else {
        if(active_burst_length_) {
          completed_bursts_.push_back(active_burst_length_);
          completed_burst_reads_+=active_burst_length_;
          while(completed_burst_reads_>std::max<size_t>(2,o.window)) {
            completed_burst_reads_-=completed_bursts_.front();completed_bursts_.pop_front();
          }
        }
        active_burst_key_=key;active_burst_length_=1;
      }
    }
    if(o.causal_window) {
      if(!recent_history_.empty() && recent_history_.back().first==key)++adjacent_repeats_;
      if(auto it=recent_shared_.find(key);it!=recent_shared_.end())collision_pairs_+=2*it->second.size();
      recent_history_.push_back({key,gpu});
      recent_shared_[key].push_back(observations_);
      recent_domains_[gpu][key].push_back(observations_);
      while(recent_history_.size()>std::max<size_t>(2,o.window)) {
        const auto old=recent_history_.front();recent_history_.pop_front();
        if(!recent_history_.empty() && recent_history_.front().first==old.first)--adjacent_repeats_;
        auto& shared=recent_shared_.at(old.first);collision_pairs_-=2*(shared.size()-1);shared.pop_front();
        if(shared.empty())recent_shared_.erase(old.first);
        auto& domain=recent_domains_.at(old.second);
        auto& positions=domain.at(old.first);positions.pop_front();
        if(positions.empty())domain.erase(old.first);
        if(domain.empty())recent_domains_.erase(old.second);
      }
    }
    if(o.adaptive_control) {
      const double n=recent_history_.size();
      double repeats=adjacent_repeats_,collision=collision_pairs_;
      if(!o.efficient_planning) {
        repeats=collision=0;
        for(size_t i=1;i<recent_history_.size();++i)
          repeats+=recent_history_[i].first==recent_history_[i-1].first;
        for(const auto& [key,positions]:recent_shared_) {
          (void)key;const double count=positions.size();collision+=count*(count-1);
        }
      }
      const double iid=n>1?collision/(n*(n-1)):0;
      const double adjacent=n>1?repeats/(n-1):0;
      // A continuous signal: random interleavings do not imply overdue reuse.
      temporal_strength_=n>=8 && iid<1?std::clamp(4*(adjacent-iid)/(1-iid),0.0,1.0):0;
    }
    auto& d=domains_[gpu];
    if(d.last_observation && observations_-d.last_observation>=std::max<size_t>(8,o.affinity_window/4)) {
      d.epoch_reads=0;d.epoch_pending=true;
    }
    d.last_observation=observations_;++d.epoch_reads;
    ++d.counts[key];d.history.push_back(key);
    if(o.track_affinity) {
      affinity_history_.emplace_back(key,gpu);++affinity_counts_[key][gpu];
      while(affinity_history_.size()>std::max<size_t>(2,o.affinity_window)) {
        const auto old=affinity_history_.front();affinity_history_.pop_front();
        auto& counts=affinity_counts_.at(old.first);
        if(--counts.at(old.second)==0)counts.erase(old.second);
        if(counts.empty())affinity_counts_.erase(old.first);
      }
    }
    d.misses=local_hit?0:d.misses+1;
    bool reset=false;
    const size_t k=std::max<size_t>(4,o.shift_window);
    if(!o.causal_window && o.aging && o.shift_reset && d.misses>=k && d.history.size()>k) {
      std::unordered_set<std::string> latest(d.history.end()-k,d.history.end());
      // Repeated misses to a small new working set indicate stale resident heat.
      // A stream of one-off misses must not erase useful frequency history.
      if(latest.size()<=k/2) {
        uint64_t stale_peak=0,current_peak=0;
        for(const auto& [observed,count]:d.counts) {
          if(latest.count(observed))current_peak=std::max(current_peak,count);
          else stale_peak=std::max(stale_peak,count);
        }
        // Repeated misses alone also occur while a stable working set is still
        // accumulating enough reuse to repay copying. Reset only with dominant
        // OLD demand outside the recent set; otherwise periodic resets can make
        // admission impossible even for an indefinitely repeated four-object loop.
        if(stale_peak>=k && stale_peak>2*current_peak) {
          while(d.history.size()>k) {
            auto found=d.counts.find(d.history.front());
            if(--found->second==0){d.forecasts.erase(found->first);d.counts.erase(found);}
            d.history.pop_front();
          }
          d.misses=0;reset=true;
        }
      }
    }
    if(o.aging) while(d.history.size()>std::max<size_t>(2,o.window)) {
      auto found=d.counts.find(d.history.front());
      if(--found->second==0){d.forecasts.erase(found->first);d.counts.erase(found);}
      d.history.pop_front();
    }
    // No-aging is an explicit ablation using cumulative frequencies. Avoid an
    // additional unbounded event log; its per-key counters are reported separately.
    if(!o.aging)d.history.clear();
    if(o.track_affinity && o.affinity_recent_demand && o.affinity_handover_epoch && d.epoch_pending) {
      if(d.epoch_reads>8)d.epoch_pending=false;
      else if(HandoverCount(gpu,key,o)>Count(gpu,key)) {
        d.epoch_pending=false;
        // A returning destination now requests an established hot object from
        // another domain. Retain all observations since this activation, but
        // do not let a prior task's local popularity block the transferred task.
        // The disabled comparator records the same epoch boundaries.
        if(o.affinity_gate && d.history.size()>d.epoch_reads) {
          while(d.history.size()>d.epoch_reads) {
            auto found=d.counts.find(d.history.front());
            if(--found->second==0){d.forecasts.erase(found->first);d.counts.erase(found);}
            d.history.pop_front();
          }
          d.misses=0;
          if(affinity_reset)*affinity_reset=true;
        }
      }
    }
    if(o.track_affinity && o.affinity_recent_demand) {
      const auto estimate=HandoverCount(gpu,key,o);
      if(estimate>Count(gpu,key))d.forecasts[key]={estimate,observations_};
      for(auto it=d.forecasts.begin();it!=d.forecasts.end();) {
        if(observations_-it->second.at>=std::max<size_t>(2,o.affinity_window))it=d.forecasts.erase(it);
        else ++it;
      }
    }
    return reset;
  }
  void ReadSample(bool local,uint64_t bytes,uint64_t micros,bool warmup=false) {
    if(!bytes || !micros)return;
    std::lock_guard<std::mutex> lock(mu_);
    Update(local?local_:remote_,double(micros)/bytes,warmup);
  }
  void CopySample(uint64_t bytes,uint64_t micros,bool warmup=false) {
    if(!bytes || !micros)return;
    std::lock_guard<std::mutex> lock(mu_);Update(copy_,double(micros)/bytes,warmup);
  }
  size_t Entries() const {
    std::lock_guard<std::mutex> lock(mu_);size_t n=0;
    for(const auto& p:domains_)n+=p.second.counts.size();
    return n;
  }
  uint64_t Frequency(int gpu,const std::string& key) const {
    std::lock_guard<std::mutex> lock(mu_);return Count(gpu,key);
  }
  uint64_t AdmissionFrequency(int gpu,const std::string& key,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);return EffectiveCount(gpu,key,o,true);
  }
  bool HasReuseEvidence(int gpu,const std::string& key,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);
    return o.adaptive_control || EffectiveCount(gpu,key,o,true)>=2 || BurstRemaining(key,o)>0 || PersistentEstimate(key,o)>0;
  }
  std::vector<Item> Ranked(int gpu,std::vector<Item> items,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);Sort(gpu,items,o);return items;
  }
  Decision Plan(int gpu,const Item& incoming,std::vector<Item> residents,
                uint64_t used,uint64_t quota,const Options& o) const {
    return PlanImpl(gpu,incoming,std::move(residents),used,quota,o,false);
  }
  // An optimistic rejection test only: omits resident loss and resident noise,
  // but preserves real headroom, admission, incoming noise and copy costs.
  // Never use its victim-free result to execute a migration.
  bool PotentiallyProfitable(int gpu,const Item& incoming,uint64_t used,
                             uint64_t quota,const Options& o) const {
    return PlanImpl(gpu,incoming,{},used,quota,o,true).allowed;
  }
 private:
  Decision PlanImpl(int gpu,const Item& incoming,std::vector<Item> residents,
                    uint64_t used,uint64_t quota,const Options& o,bool optimistic) const {
    std::lock_guard<std::mutex> lock(mu_);Decision result;
    if(incoming.bytes>quota){result.reason="oversize";return result;}
    const uint64_t needed=used>quota ? used-quota+incoming.bytes : (incoming.bytes>quota-used ? incoming.bytes-(quota-used) : 0);
    const auto frequency=Count(gpu,incoming.key);
    result.incoming_count=frequency;
    result.affinity_incoming_count=EffectiveCount(gpu,incoming.key,o,true);
    result.affinity_adjusted_items=result.affinity_incoming_count!=frequency;
    for(const auto& resident:residents)
      result.affinity_adjusted_items+=EffectiveCount(gpu,resident.key,o,false)!=Count(gpu,resident.key);
    if(!o.static_reuse_value) {
      result.survival_adjusted_items=Survival(gpu,incoming.key,o)<1.0;
      for(const auto& resident:residents)
        result.survival_adjusted_items+=Survival(gpu,resident.key,o)<1.0;
    }
    if(o.persistent_run_reuse && !o.static_reuse_value) {
      result.persistent_reuse_adjusted_items=PersistentEstimate(incoming.key,o)>RecentValue(gpu,incoming.key,o,true);
      for(const auto& resident:residents)
        result.persistent_reuse_adjusted_items+=PersistentEstimate(resident.key,o)>RecentValue(gpu,resident.key,o,false);
    }
    result.costs_calibrated=remote_.n && local_.n && copy_.n;
    result.burst_remaining=BurstRemaining(incoming.key,o);
    result.cohort_disk_reuse=CohortDiskReuse(gpu,incoming.key,o);
    // Exploration is quota bounded, never displacing a resident. Completed
    // runs may justify more than one remote read of exploration cost; the
    // current unfinished run is censored and cannot inflate this budget.
    if(o.reuse_scaled_exploration && o.burst_reuse && !completed_bursts_.empty())
      result.exploration_reads=std::max(1.0,double(completed_burst_reads_)/completed_bursts_.size());
    if(o.adaptive_control && !needed && (o.bounded_cost_warmup || !copy_.n || copy_.mean<=result.exploration_reads*(remote_.n?remote_.mean:0.01))) {
      result.allowed=true;result.explore_headroom=true;result.reason=o.bounded_cost_warmup?"capacity_bounded_calibration":"free_headroom_exploration";
      result.incoming_us=Value(gpu,incoming,o,true);
      result.copy_us=incoming.bytes*(copy_.n?copy_.mean:(remote_.n?remote_.mean:0.01));
      return result;
    }
    if(o.admission && result.affinity_incoming_count<2 && result.burst_remaining<=0 && PersistentEstimate(incoming.key,o)<=0 && result.cohort_disk_reuse<=0){result.reason="no_reuse";return result;}
    if(o.admission && o.affinity_gate && !o.affinity_recent_demand) {
      const auto found=affinity_counts_.find(incoming.key);
      uint64_t own=0,peak=0;
      if(found!=affinity_counts_.end())for(const auto& [node,n]:found->second) {
        peak=std::max(peak,n);if(node==gpu)own=n;
      }
      // Equal sharing permits replicas; incidental readers of a strongly
      // concentrated object do not pollute their private cache. No phase oracle.
      if(!own || own*2<peak){result.reason="affinity";return result;}
    }
    Sort(gpu,residents,o);
    uint64_t freed=0;double victim_uncertainty=0;
    for(const auto& victim:residents) {
      if(freed>=needed)break;
      freed+=victim.bytes;result.victims.push_back(victim.key);
      result.displaced_us+=Value(gpu,victim,o,false);
      victim_uncertainty+=std::sqrt(double(EffectiveCount(gpu,victim.key,o,false)))*victim.bytes*victim.coverage;
    }
    if(!optimistic && freed<needed){result.reason="pinned_capacity";return result;}
    result.incoming_us=Value(gpu,incoming,o,true);
    // Cold start: before samples exist, assume one remote read of copy cost and
    // half its service time as potential savings. This prior is recorded, then
    // replaced by online measurements; no synthetic delay is injected.
    result.copy_us=o.cost ? incoming.bytes*(copy_.n?copy_.mean:(remote_.n?remote_.mean:0.01)) : 0;
    if(o.adaptive_control && (optimistic?needed>0:!result.victims.empty())) {
      // A heuristic noise margin, not a statistical confidence interval. Only
      // weak temporal evidence is penalized; burst benefit stays responsive.
      result.uncertainty_us=(1-temporal_strength_)*DiskReuseScale(o)*SavingRate()*
          (std::sqrt(double(result.affinity_incoming_count))*incoming.bytes+victim_uncertainty);
    }
    const double charged_loss=o.joint_admission?result.displaced_us+result.uncertainty_us:0;
    if(o.admission && result.incoming_us<=charged_loss+result.copy_us) {
      result.reason=result.incoming_us<=result.copy_us?"copy_cost":"victim_loss";
      return result;
    }
    result.allowed=true;result.reason=o.joint_admission?"net_gain":"independent_gain";return result;
  }
 private:
  struct Rate {double mean=0;uint64_t n=0;};
  struct Forecast {uint64_t count=0,at=0;};
  struct Domain {uint64_t last_observation=0,epoch_reads=0;bool epoch_pending=false;std::unordered_map<std::string,Forecast> forecasts;size_t misses=0;std::deque<std::string> history;std::unordered_map<std::string,uint64_t> counts;};
  static void Update(Rate& r,double value,bool warmup) {
    // Use equal weights while collecting the first 20 samples, then retain
    // the existing 5% EWMA. A single slow first sample must not carry >50%
    // weight after twelve later observations.
    const double alpha=warmup?1.0/std::min<uint64_t>(20,r.n+1):0.05;
    r.mean=r.n?(1.0-alpha)*r.mean+alpha*value:value;++r.n;
  }
  uint64_t Count(int gpu,const std::string& key) const {
    const auto domain=domains_.find(gpu);if(domain==domains_.end())return 0;
    const auto item=domain->second.counts.find(key);return item==domain->second.counts.end()?0:item->second;
  }
  double SavingRate() const {
    const double remote=remote_.n?remote_.mean:0.01;
    const double local=local_.n?local_.mean:remote*0.5;
    return std::max(0.0,remote-local);
  }
  uint64_t EffectiveCount(int gpu,const std::string& key,const Options& o,bool incoming) const {
    const auto domain_count=Count(gpu,key);
    if(o.causal_window) {
      const auto* positions=RecentPositions(gpu,key,o);
      return positions?positions->size():0;
    }
    if(o.shared_value) {
      uint64_t total=0;
      // Count actual consumers, not the location holding the one shared copy.
      // H's per-consumer history reset is reflected in both arrival and victim values.
      for(const auto& [node,domain]:domains_) {
        (void)node;
        auto found=domain.counts.find(key);
        if(found!=domain.counts.end())total+=found->second;
      }
      return total;
    }
    (void)incoming;
    if(!o.affinity_gate || !o.affinity_recent_demand)return domain_count;
    const auto domain=domains_.find(gpu);
    if(!domain_count || domain==domains_.end())return domain_count;
    const auto forecast=domain->second.forecasts.find(key);
    if(forecast==domain->second.forecasts.end())return domain_count;
    const uint64_t lifetime=std::max<size_t>(2,o.affinity_window);
    const auto age=observations_-forecast->second.at;
    return age>=lifetime?domain_count:std::max(domain_count,forecast->second.count*(lifetime-age)/lifetime);
  }
  uint64_t HandoverCount(int gpu,const std::string& key,const Options& o) const {
    (void)o;
    const auto domain_count=Count(gpu,key);
    const auto object=affinity_counts_.find(key);
    if(!domain_count || object==affinity_counts_.end())return domain_count;
    uint64_t total=0,own=0;
    for(const auto& [node,count]:object->second){total+=count;if(node==gpu)own=count;}
    constexpr size_t short_window=4;
    if(!own || total<8 || total-own<2*own || affinity_history_.size()<short_window)return domain_count;
    uint64_t short_own=0,long_own=0;size_t index=0;
    for(auto it=affinity_history_.rbegin();it!=affinity_history_.rend();++it,++index)
      if(it->second==gpu){++long_own;if(index<short_window)++short_own;}
    // Borrow reuse only after observed destination activity becomes concentrated
    // AND at least doubles its long-window share. The object must already have
    // strong reuse elsewhere. No workload labels, future accesses or prefetch.
    // Use the SAME estimate for an arrival and a resident: newly copied hot
    // replicas must not immediately become artificially cheap eviction victims.
    // Stable/balanced domains retain their original estimate.
    if(short_own*4<3*short_window || short_own*affinity_history_.size()<2*short_window*long_own)return domain_count;
    return std::max(domain_count,total*short_own/short_window);
  }
  const std::deque<uint64_t>* RecentPositions(int gpu,const std::string& key,const Options& o) const {
    if(o.shared_value) {
      const auto found=recent_shared_.find(key);
      return found==recent_shared_.end()?nullptr:&found->second;
    }
    const auto domain=recent_domains_.find(gpu);
    if(domain==recent_domains_.end())return nullptr;
    const auto found=domain->second.find(key);
    return found==domain->second.end()?nullptr:&found->second;
  }
  double Survival(int gpu,const std::string& key,const Options& o) const {
    if(!o.causal_window || !o.shift_reset)return 1.0;
    const auto* positions=RecentPositions(gpu,key,o);
    if(!positions || positions->size()<2)return 1.0;
    // Past inter-arrival spacing sets the half-life. An unrequested resident
    // loses value as its next reuse becomes overdue. Arrivals and residents use
    // exactly the same forecast; there is no phase label or cache-state oracle.
    double gap=double(positions->back()-positions->front())/(positions->size()-1);
    if(o.burst_interval_survival && o.burst_reuse) {
      // Consecutive reads within a run do not measure how soon that run will
      // recur. Use completed between-run gaps when recurrence was observed.
      // One-off bursts retain the original short half-life. No future run,
      // workload label or permanent hot-key exemption is used.
      uint64_t elapsed=0,intervals=0;
      for(size_t i=1;i<positions->size();++i) {
        const auto distance=(*positions)[i]-(*positions)[i-1];
        if(distance>1){elapsed+=distance;++intervals;}
      }
      if(intervals)gap=double(elapsed)/intervals;
    }
    return std::exp2(-(o.adaptive_control?temporal_strength_:1.0)*double(observations_-positions->back())/std::max(4.0,gap));
  }
  double DiskReuseScale(const Options& o) const {
    // A completed run contributes one potential disk miss when its retained
    // capture is gone. Adjacent reads are already served by the shared RAM tier.
    return o.retained_capture && completed_burst_reads_?
      double(completed_bursts_.size())/completed_burst_reads_:1.0;
  }
  double BurstRemaining(const std::string& key,const Options& o) const {
    if(o.retained_capture)return 0;
    if(!o.burst_reuse || !o.causal_window || !o.shared_value || key!=active_burst_key_ || completed_bursts_.size()<8)return 0;
    // Conditional residual length of completed runs only. The active run is
    // censored: never use its eventual length. Two zero-residual pseudo-runs
    // shrink a sparse estimate; no workload labels or fixed burst length.
    double remaining=0,eligible=2;
    for(const auto length:completed_bursts_)if(length>=active_burst_length_) {
      remaining+=length-active_burst_length_;++eligible;
    }
    return remaining/eligible;
  }
  bool DiskOpportunityEnabled(const Options& o) const {
    return o.disk_opportunity_value && !o.static_reuse_value && o.retained_capture &&
      o.persistent_run_reuse && o.causal_window && o.shared_value && o.burst_reuse;
  }
  double PersistentEstimate(const std::string& key,const Options& o) const {
    if(DiskOpportunityEnabled(o))
      return run_reuse_.DiskOpportunity(key,observations_,o.window)/DiskReuseScale(o);
    return o.persistent_run_reuse && o.causal_window && o.shared_value && o.burst_reuse?
      run_reuse_.Estimate(key,observations_,o.window,o.persistent_reuse_immediate_decay):0.0;
  }
  double RecentValue(int gpu,const std::string& key,const Options& o,bool incoming) const {
    double repeats=double(EffectiveCount(gpu,key,o,incoming));
    // Use the same repeat-evidence estimate for arrivals and residents. Charging
    // resident frequency in full while subtracting one only from the incoming
    // object would add an unintended incumbent preference to the cost ablation.
    if(!o.frequency_admission)repeats=std::max(0.0,repeats-1.0);
    return repeats*Survival(gpu,key,o);
  }
  double CohortDiskReuse(int gpu,const std::string& key,const Options& o) const {
    if(DiskOpportunityEnabled(o))return 0;
    if(!o.cohort_reuse_prior || o.static_reuse_value || !o.retained_capture ||
       !o.persistent_run_reuse || !o.causal_window || !o.shared_value ||
       !o.burst_reuse || !o.adaptive_control)return 0;
    (void)gpu;return temporal_strength_*run_reuse_.NewcomerDiskPrior(key)*run_reuse_.NewcomerSurvival(key,observations_);
  }
  double Value(int gpu,const Item& item,const Options& o,bool incoming) const {
    if(o.static_reuse_value) {
      double repeats=double(EffectiveCount(gpu,item.key,o,incoming));
      if(!o.frequency_admission)repeats=std::max(0.0,repeats-1.0);
      return repeats*DiskReuseScale(o)*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;
    }
    if(DiskOpportunityEnabled(o)) {
      const double recent=RecentValue(gpu,item.key,o,incoming)*DiskReuseScale(o);
      const double opportunity=run_reuse_.DiskOpportunity(item.key,observations_,o.window);
      const double competition=o.novel_reuse_decay?1.0-(o.adaptive_control?temporal_strength_:1.0)*(1.0-run_reuse_.CompetitionSurvival(item.key)):1.0;
      // Recent and long-run forecasts overlap: never add their predictions.
      const double repeats=std::max(recent,opportunity*competition);
      return repeats*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;
    }
    const double recent=RecentValue(gpu,item.key,o,incoming);
    const double persistent=PersistentEstimate(item.key,o);
    double past=std::max(recent,persistent);
    if(o.novel_reuse_decay && o.persistent_run_reuse && o.causal_window && o.shared_value && o.burst_reuse) {
      const double competition=1.0-(o.adaptive_control?temporal_strength_:1.0)*(1.0-run_reuse_.CompetitionSurvival(item.key));
      // Competition can discount extrapolated long-history demand, but must
      // not erase already age-discounted observations in the recent window.
      past=o.recent_value_floor?std::max(recent,persistent*competition):past*competition;
    }
    // These are overlapping estimates, not independent demand to add together.
    // Use the same value for incoming and resident copies of the current key.
    return std::max({past*DiskReuseScale(o),BurstRemaining(item.key,o),CohortDiskReuse(gpu,item.key,o)})*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;
  }
  void Sort(int gpu,std::vector<Item>& items,const Options& o) const {
    if(o.efficient_planning && o.value_victim) {
      // Value is pure under mu_: compute it once per resident, not twice per
      // sort comparison. Keep the same floating-point operation and tie order.
      struct Scored {Item item;double score;};
      std::vector<Scored> scored;scored.reserve(items.size());
      for(auto& item:items) {
        const double score=Value(gpu,item,o,false)/(o.size_aware?std::max<uint64_t>(1,item.bytes):1);
        scored.push_back({std::move(item),score});
      }
      std::sort(scored.begin(),scored.end(),[](const Scored& a,const Scored& b){
        if(a.score!=b.score)return a.score<b.score;
        if(a.item.recency!=b.item.recency)return a.item.recency<b.item.recency;
        return a.item.key<b.item.key;
      });
      items.clear();for(auto& value:scored)items.push_back(std::move(value.item));
      return;
    }
    std::sort(items.begin(),items.end(),[&](const Item& a,const Item& b){
      if(o.value_victim) {
        const double av=Value(gpu,a,o,false)/(o.size_aware?std::max<uint64_t>(1,a.bytes):1);
        const double bv=Value(gpu,b,o,false)/(o.size_aware?std::max<uint64_t>(1,b.bytes):1);
        if(av!=bv)return av<bv;
      }
      if(a.recency!=b.recency)return a.recency<b.recency;
      return a.key<b.key;
    });
  }
  mutable std::mutex mu_;
  std::unordered_map<int,Domain> domains_;
  std::deque<std::pair<std::string,int>> affinity_history_;
  std::unordered_map<std::string,std::unordered_map<int,uint64_t>> affinity_counts_;
  std::deque<std::pair<std::string,int>> recent_history_;
  std::unordered_map<std::string,std::deque<uint64_t>> recent_shared_;
  std::unordered_map<int,std::unordered_map<std::string,std::deque<uint64_t>>> recent_domains_;
  uint64_t observations_=0;
  uint64_t adjacent_repeats_=0,collision_pairs_=0;
  double temporal_strength_=0;
  std::string active_burst_key_;
  uint64_t active_burst_length_=0,completed_burst_reads_=0;
  std::deque<uint64_t> completed_bursts_;
  Rate local_,remote_,copy_;
  RunReuse run_reuse_;
};
}
