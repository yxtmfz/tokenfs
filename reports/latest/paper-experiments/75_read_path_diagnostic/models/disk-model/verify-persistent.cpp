#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <cassert>
#include <iostream>
#include "run_reuse.h"
#define private public
#include "measured_policy.h"
#undef private
using namespace tokenfs_policy;
Options opts(){Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;o.disk_opportunity_value=true;o.recent_value_floor=true;o.cohort_reuse_prior=true;return o;}
void observe(MeasuredPolicy&p,const std::string&key,const Options&o,bool disk=true){p.Observe(0,key,o,false,nullptr,disk);}
int main(int argc,char**argv){
 const bool logical=std::string(argv[1])=="logical";auto o=opts();MeasuredPolicy p;
 observe(p,"a",o);assert(p.LongDiskDemand("a",o)==0);
 for(int i=0;i<9;++i)observe(p,"other",o);observe(p,"a",o);
 assert(p.disk_long_.at("a").mean==10);assert(p.disk_long_.at("a").n==1);assert(std::abs(p.LongDiskDemand("a",o)-6.4)<1e-10);
 // A storage read counts even if the preceding storage event has the same key.
 observe(p,"a",o);assert(p.disk_long_.at("a").n==2);assert(std::abs(p.disk_long_.at("a").mean-5.5)<1e-10);
 const auto before=p.disk_long_.at("a");const double forecast=p.LongDiskDemand("a",o);
 for(int i=0;i<200;++i)observe(p,"a",o,false);
 const auto after=p.disk_long_.at("a");assert(before.n==after.n && before.mean==after.mean && before.last==after.last);
 assert(logical?p.LongDiskDemand("a",o)<forecast:p.LongDiskDemand("a",o)==forecast);
 for(int i=0;i<1000;++i)observe(p,std::to_string(i),o);
 assert(p.disk_long_events_.size()<=o.window && p.disk_long_.size()<=o.window);assert(!p.disk_long_.count("a"));
 std::cout<<"completed gaps only, consecutive storage events retained, RAM excludes training, persistent forecast decay and bounds passed\n";
}
