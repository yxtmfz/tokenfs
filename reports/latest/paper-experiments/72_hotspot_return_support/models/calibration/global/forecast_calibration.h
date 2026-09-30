#pragma once
#include <algorithm>
#include <array>
#include <deque>
#include <string>
#include <unordered_map>
#include <utility>
#include <cstdint>
namespace tokenfs_policy {
// Delayed prequential evaluation: score only requests observed after a forecast.
// One outstanding forecast per key; expiration includes zero-return outcomes.
class ForecastCalibration {
 public:
  void Observe(const std::string& key,uint64_t at,bool disk) {
    if(disk) {auto it=pending_.find(key);if(it!=pending_.end())++it->second.actual;}
    while(!expiry_.empty() && expiry_.front().first<=at) {
      auto it=pending_.find(expiry_.front().second);const auto p=it->second;
      auto& loss=losses_[p.group];
      loss.push_back({(p.base-p.actual)*(p.base-p.actual),(p.dynamic-p.actual)*(p.dynamic-p.actual)});
      if(loss.size()>p.horizon)loss.pop_front();
      pending_.erase(it);expiry_.pop_front();
    }
  }
  void Predict(const std::string& key,uint64_t at,size_t horizon,double base,double dynamic,size_t group) {
    if(pending_.count(key))return;
    horizon=std::max<size_t>(2,horizon);
    pending_.emplace(key,Trial{base,dynamic,0,group,horizon});expiry_.push_back({at+horizon,key});
  }
  double Weight(size_t group) const {
    double base=0,dynamic=0;
    for(const auto& x:losses_[group]){base+=x.first;dynamic+=x.second;}
    return dynamic<base?1.0:0.0;
  }
  size_t Pending()const{return pending_.size();}
  size_t Completed(size_t group)const{return losses_[group].size();}
 private:
  struct Trial {double base,dynamic,actual;size_t group,horizon;};
  std::unordered_map<std::string,Trial> pending_;
  std::deque<std::pair<uint64_t,std::string>> expiry_;
  std::array<std::deque<std::pair<double,double>>,2> losses_;
};
}
