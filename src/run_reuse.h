#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstddef>
#include <utility>
#include <deque>
#include <string>
#include <unordered_map>

namespace tokenfs_policy {
// Bounded summary of observed runs, independent of the short request window.
// Access is serialized by MeasuredPolicy::mu_. No cache-state or trace labels.
class RunReuse {
 public:
  void Observe(const std::string& key,uint64_t at,size_t limit) {
    limit=std::max<size_t>(2,limit);
    if(active_length_ && key==active_) {
      ++active_length_;entries_.at(key).last_seen=at;entries_.at(key).novelty_seen=novelty_;
    } else {
      if(active_length_)entries_.at(active_).length.Add(active_length_,limit);
      auto& entry=entries_[key];
      if(entry.last_start) {
        // A return in a distinct run establishes new recurring demand.
        // Adjacent repeats and one-off scans never advance this clock.
        if(!entry.gap.n){++novelty_;++recurrent_entries_;}
        entry.gap.Add(at-entry.last_start,limit);
        return_gaps_.push_back(at-entry.last_start);return_gap_sum_+=at-entry.last_start;
      }
      entry.novelty_seen=novelty_;
      entry.last_start=entry.last_seen=at;entry.generation=++generation_;
      recent_.emplace_back(key,generation_);
      active_=key;active_length_=1;
    }
    while(return_gaps_.size()>limit){return_gap_sum_-=return_gaps_.front();return_gaps_.pop_front();}
    while(recent_.size()>limit) {
      const auto old=recent_.front();recent_.pop_front();
      auto it=entries_.find(old.first);
      if(it!=entries_.end() && it->second.generation==old.second) {
        if(it->second.gap.n)--recurrent_entries_;
        entries_.erase(it);
      }
    }
  }
  double Estimate(const std::string& key,uint64_t at,size_t horizon,bool immediate_decay=false) const {
    auto it=entries_.find(key);if(it==entries_.end())return 0;
    const auto& e=it->second;
    if(!e.gap.n || !e.length.n)return 0; // A single burst is not recurrence.
    const double interval=std::max(4.0,e.gap.mean);
    // One observed standard deviation is a heuristic grace for irregular
    // arrivals, not a statistical confidence bound. Stale keys still decay.
    const double grace=immediate_decay?0.0:interval+std::sqrt(std::max(0.0,e.gap.variance));
    const double overdue=std::max(0.0,double(at-e.last_seen)-grace);
    const double confidence=double(e.gap.n)/(e.gap.n+1.0);
    return std::max<size_t>(2,horizon)/interval*e.length.mean*confidence*
           std::exp2(-overdue/interval);
  }
  double CompetitionSurvival(const std::string& key) const {
    const auto it=entries_.find(key);
    return it==entries_.end()?1.0:std::exp2(-double(novelty_-it->second.novelty_seen));
  }
  double NewcomerDiskPrior(const std::string& key,bool object_weighted=false) const {
    const auto it=entries_.find(key);
    if(it==entries_.end() || it->second.gap.n || recent_.size()<=entries_.size())return 0;
    // Each retained object supplies at most one piece of return evidence.
    // Many returns of the same hot object cannot increase this numerator.
    // This is bounded object support, not a calibrated return probability:
    // objects have unequal ages and unfinished observation windows.
    if(object_weighted)return double(recurrent_entries_)/(entries_.size()+1.0);
    // Transfer bounded evidence from observed returns, not the current run's
    // eventual length. One pseudo-object shrinks sparse histories; at most one
    // future disk read is credited to a not-yet-recurring object.
    return std::min(1.0,double(recent_.size()-entries_.size())/(entries_.size()+1.0));
  }
  // New objects borrow a between-run interval, not the adjacent-read gap
  // within their first burst. Observed return gaps are bounded by the same
  // run-history budget; an unfinished burst contributes no new interval.
  double NewcomerSurvival(const std::string& key,uint64_t at) const {
    const auto it=entries_.find(key);
    if(it==entries_.end() || return_gaps_.empty())return 0;
    return std::exp2(-double(at-it->second.last_seen)/std::max(4.0,double(return_gap_sum_)/return_gaps_.size()));
  }
  // Count one possible disk reuse per distinct observed run, not its adjacent
  // RAM-served requests. Do not expire recurrence before its observed mean gap.
  // The forecast uses completed gaps only; overdue reuse still loses value.
  double DiskOpportunity(const std::string& key,uint64_t at,size_t horizon) const {
    const auto it=entries_.find(key);if(it==entries_.end())return 0;
    const auto& e=it->second;if(!e.gap.n)return 0;
    const double gap=std::max(4.0,e.gap.mean);
    const double age=double(at-e.last_start);
    const double confidence=double(e.gap.n)/(e.gap.n+1.0);
    return double(horizon)/gap*confidence*std::exp2(-std::max(0.0,age-gap)/gap);
  }
  size_t Entries() const {return entries_.size();}
  size_t Runs() const {return recent_.size();}
  size_t ReturnIntervals() const {return return_gaps_.size();}
  size_t RecurrentEntries() const {return recurrent_entries_;}
 private:
  struct Moment {
    uint64_t n=0;double mean=0,variance=0;
    void Add(double value,size_t limit) {
      n=std::min<uint64_t>(n+1,limit);
      const double alpha=1.0/n,delta=value-mean;
      mean+=alpha*delta;variance=(1-alpha)*(variance+alpha*delta*delta);
    }
  };
  struct Entry {Moment gap,length;uint64_t last_start=0,last_seen=0,generation=0,novelty_seen=0;};
  std::unordered_map<std::string,Entry> entries_;
  std::deque<std::pair<std::string,uint64_t>> recent_;
  std::deque<uint64_t> return_gaps_;uint64_t return_gap_sum_=0;
  std::string active_;
  uint64_t active_length_=0,generation_=0,novelty_=0;
  size_t recurrent_entries_=0;
};
}
