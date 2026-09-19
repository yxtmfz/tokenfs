#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <unordered_map>
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
};
struct Decision {
  bool allowed=false;
  std::string reason;
  double incoming_us=0, displaced_us=0, copy_us=0;
  std::vector<std::string> victims;
};

class MeasuredPolicy {
 public:
  void Observe(int gpu,const std::string& key,const Options& o) {
    std::lock_guard<std::mutex> lock(mu_);
    auto& d=domains_[gpu];++d.counts[key];d.history.push_back(key);
    if(o.aging) while(d.history.size()>std::max<size_t>(2,o.window)) {
      auto found=d.counts.find(d.history.front());
      if(--found->second==0)d.counts.erase(found);
      d.history.pop_front();
    }
    // No-aging is an explicit ablation using cumulative frequencies. Avoid an
    // additional unbounded event log; its per-key counters are reported separately.
    if(!o.aging)d.history.clear();
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
  std::vector<Item> Ranked(int gpu,std::vector<Item> items,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);Sort(gpu,items,o);return items;
  }
  Decision Plan(int gpu,const Item& incoming,std::vector<Item> residents,
                uint64_t used,uint64_t quota,const Options& o) const {
    std::lock_guard<std::mutex> lock(mu_);Decision result;
    if(incoming.bytes>quota){result.reason="oversize";return result;}
    const auto frequency=Count(gpu,incoming.key);
    if(o.admission && frequency<2){result.reason="no_reuse";return result;}
    Sort(gpu,residents,o);
    uint64_t freed=0;const auto needed=incoming.bytes>quota-std::min(used,quota)?incoming.bytes-(quota-std::min(used,quota)):0;
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
    if(o.admission && result.incoming_us<=result.displaced_us+result.copy_us) {
      result.reason=result.incoming_us<=result.copy_us?"copy_cost":"victim_loss";
      return result;
    }
    result.allowed=true;result.reason="net_gain";return result;
  }
 private:
  struct Rate {double mean=0;uint64_t n=0;};
  struct Domain {std::deque<std::string> history;std::unordered_map<std::string,uint64_t> counts;};
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
  double Value(int gpu,const Item& item,const Options& o,bool incoming) const {
    double repeats=double(Count(gpu,item.key));
    if(incoming && o.cost)repeats=std::max(0.0,repeats-1.0); // Current miss cannot become a hit.
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
  Rate local_,remote_,copy_;
};
}
