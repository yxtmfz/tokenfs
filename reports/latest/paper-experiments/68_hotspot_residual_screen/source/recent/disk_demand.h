#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <string>
#include <unordered_map>
namespace tokenfs_policy {
// A causal summary of observed reads that actually reach a disk tier.
// RAM-served requests advance age but are not counted as disk reuse.
class DiskDemand {
 public:
  void Observe(const std::string& key,uint64_t at,size_t horizon,bool captured) {
    horizon=std::max<size_t>(2,horizon);
    if(!captured) {
      auto& e=entries_[key];
      if(e.last) {
        e.n=std::min<uint64_t>(e.n+1,horizon);
        const double delta=double(at-e.last)-e.mean,alpha=1.0/e.n;
        e.mean+=alpha*delta;e.variance=(1-alpha)*(e.variance+alpha*delta*delta);
      }
      e.last=at;e.generation=++generation_;
      long_.emplace_back(key,generation_);
      recent_.emplace_back(key,at);++counts_[key];
    }
    while(!recent_.empty() && at-recent_.front().second>=horizon) {
      const auto k=recent_.front().first;recent_.pop_front();
      if(--counts_.at(k)==0)counts_.erase(k);
    }
    while(long_.size()>horizon) {
      auto old=long_.front();long_.pop_front();
      auto it=entries_.find(old.first);
      if(it!=entries_.end() && it->second.generation==old.second)entries_.erase(it);
    }
  }
  double Value(const std::string& key,uint64_t at,size_t horizon) const {
    auto it=entries_.find(key);if(it==entries_.end() || !it->second.n)return 0;
    const auto& e=it->second;
    const double interval=std::max(1.0,e.mean);
    const double confidence=double(e.n)/(e.n+1.0);
    const double forecast=std::max<size_t>(2,horizon)/interval*confidence;
    auto c=counts_.find(key);
    const double recent=c==counts_.end()?0:std::max(0.0,double(c->second)-1.0);
    return recent*std::exp2(-double(at-e.last)/interval);
  }
 private:
  struct Entry {uint64_t n=0,last=0,generation=0;double mean=0,variance=0;};
  std::unordered_map<std::string,Entry> entries_;
  std::unordered_map<std::string,size_t> counts_;
  std::deque<std::pair<std::string,uint64_t>> recent_,long_;
  uint64_t generation_=0;
};
}
