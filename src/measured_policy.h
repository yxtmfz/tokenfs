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

namespace tokenfs_policy {
// Recent reuse is an estimate, not future knowledge. Each domain sees only accesses
// observed so far. Rates include measured foreground I/O and verified-copy time.
struct Item { std::string key; uint64_t bytes=0; uint64_t recency=0; };
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
};
struct Decision {
  bool allowed=false;
  std::string reason;
  double incoming_us=0, displaced_us=0, copy_us=0;
  bool costs_calibrated=false;
  uint64_t incoming_count=0;
  uint64_t affinity_incoming_count=0;
  uint64_t affinity_adjusted_items=0;
  std::vector<std::string> victims;
};

class MeasuredPolicy {
 public:
  bool Observe(int gpu,const std::string& key,const Options& o,bool local_hit=false) {
    std::lock_guard<std::mutex> lock(mu_);
    auto& d=domains_[gpu];++d.counts[key];d.history.push_back(key);
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
    if(o.aging && o.shift_reset && d.misses>=k && d.history.size()>k) {
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
            if(--found->second==0)d.counts.erase(found);
            d.history.pop_front();
          }
          d.misses=0;reset=true;
        }
      }
    }
    if(o.aging) while(d.history.size()>std::max<size_t>(2,o.window)) {
      auto found=d.counts.find(d.history.front());
      if(--found->second==0)d.counts.erase(found);
      d.history.pop_front();
    }
    // No-aging is an explicit ablation using cumulative frequencies. Avoid an
    // additional unbounded event log; its per-key counters are reported separately.
    if(!o.aging)d.history.clear();
    return reset;
  }
  void ReadSample(bool local,uint64_t bytes,uint64_t micros) {
    if(!bytes || !micros)return;
    std::lock_guard<std::mutex> lock(mu_);
    Update(local?local_:remote_,double(micros)/bytes);
  }
  void CopySample(uint64_t bytes,uint64_t micros) {
    if(!bytes || !micros)return;
    std::lock_guard<std::mutex> lock(mu_);Update(copy_,double(micros)/bytes);
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
  std::vector<Item> Ranked(int gpu,std::vector<Item> items,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);Sort(gpu,items,o);return items;
  }
  Decision Plan(int gpu,const Item& incoming,std::vector<Item> residents,
                uint64_t used,uint64_t quota,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);Decision result;
    if(incoming.bytes>quota){result.reason="oversize";return result;}
    const auto frequency=Count(gpu,incoming.key);
    result.incoming_count=frequency;
    result.affinity_incoming_count=EffectiveCount(gpu,incoming.key,o,true);
    result.affinity_adjusted_items=result.affinity_incoming_count!=frequency;
    result.costs_calibrated=remote_.n && local_.n && copy_.n;
    if(o.admission && result.affinity_incoming_count<2){result.reason="no_reuse";return result;}
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
    uint64_t freed=0;const auto needed=used>quota ? used-quota+incoming.bytes : (incoming.bytes>quota-used ? incoming.bytes-(quota-used) : 0);
    for(const auto& victim:residents) {
      if(freed>=needed)break;
      freed+=victim.bytes;result.victims.push_back(victim.key);
      result.displaced_us+=Value(gpu,victim,o,false);
    }
    if(freed<needed){result.reason="pinned_capacity";return result;}
    result.incoming_us=Value(gpu,incoming,o,true);
    // Cold start: before samples exist, assume one remote read of copy cost and
    // half its service time as potential savings. This prior is recorded, then
    // replaced by online measurements; no synthetic delay is injected.
    result.copy_us=o.cost ? incoming.bytes*(copy_.n?copy_.mean:(remote_.n?remote_.mean:0.01)) : 0;
    const double charged_loss=o.joint_admission?result.displaced_us:0;
    if(o.admission && result.incoming_us<=charged_loss+result.copy_us) {
      result.reason=result.incoming_us<=result.copy_us?"copy_cost":"victim_loss";
      return result;
    }
    result.allowed=true;result.reason=o.joint_admission?"net_gain":"independent_gain";return result;
  }
 private:
  struct Rate {double mean=0;uint64_t n=0;};
  struct Domain {size_t misses=0;std::deque<std::string> history;std::unordered_map<std::string,uint64_t> counts;};
  static void Update(Rate& r,double value) {r.mean=r.n?0.95*r.mean+0.05*value:value;++r.n;}
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
    if(!incoming || !o.affinity_gate || !o.affinity_recent_demand)return domain_count;
    const auto object=affinity_counts_.find(key);
    if(object==affinity_counts_.end())return domain_count;
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
    // Stable/balanced domains and every resident retain their original estimate.
    if(short_own*4<3*short_window || short_own*affinity_history_.size()<2*short_window*long_own)return domain_count;
    return std::max(domain_count,total*short_own/short_window);
  }
  double Value(int gpu,const Item& item,const Options& o,bool incoming) const {
    double repeats=double(EffectiveCount(gpu,item.key,o,incoming));
    // Use the same repeat-evidence estimate for arrivals and residents. Charging
    // resident frequency in full while subtracting one only from the incoming
    // object would add an unintended incumbent preference to the cost ablation.
    if(!o.frequency_admission)repeats=std::max(0.0,repeats-1.0);
    return repeats*(o.cost?SavingRate()*item.bytes:1.0);
  }
  void Sort(int gpu,std::vector<Item>& items,const Options& o) const {
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
  Rate local_,remote_,copy_;
};
}
