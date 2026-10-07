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
void observe(MeasuredPolicy&p,const std::string&key,const Options&o,bool disk=true,bool local=false){p.Observe(0,key,o,local,nullptr,disk);}
int main(int argc,char**argv){
 const bool logical=std::string(argv[1])=="logical";
 auto o=opts();MeasuredPolicy p;
 observe(p,"a",o,true);assert(p.disk_positions_.at("a").size()==1);assert(p.disk_observations_==1);assert(p.DiskDemand("a",o)==0);
 for(int i=0;i<20;++i)observe(p,"a",o,false,true);
 assert(p.disk_positions_.at("a").size()==1);assert(p.disk_observations_==1);assert(p.DiskDemand("a",o)==0);
 observe(p,"b",o,true);observe(p,"a",o,true,true);
 assert(p.disk_positions_.at("a").size()==2);assert(p.disk_observations_==3);assert(p.DiskDemand("a",o)>0);
 const Item item{"a",2097152,0,1};assert(p.Value(0,item,o,true)==p.Value(0,item,o,false));
 // Local disk hits and remote reads both contribute equal demand; RAM hits do not.
 MeasuredPolicy q,r;for(int i=0;i<30;++i){auto k=std::to_string(i%4);observe(q,k,o,true,false);observe(r,k,o,true,true);}assert(q.disk_positions_==r.disk_positions_);
 // Actual event history is bounded, no scan-specific exemption or future key knowledge.
 for(int i=0;i<1000;++i)observe(p,std::to_string(i),o,true);
 assert(p.disk_history_.size()<=o.window);assert(p.disk_positions_.size()<=o.window);
 observe(p,"alive",o,true);const auto at=p.DiskClock();
 for(int i=0;i<200;++i)observe(p,"alive",o,false,true);
 assert(p.disk_observations_==1004);assert(p.DiskClock()==at+(logical?200:0));
 assert(p.disk_positions_.count("alive")==unsigned(!logical));
 // H ablation must never update or consult disk-demand histories.
 o.static_reuse_value=true;MeasuredPolicy n;for(int i=0;i<300;++i)observe(n,std::to_string(i%13),o,true);
 assert(n.disk_history_.empty());assert(n.disk_positions_.empty());assert(n.disk_observations_==0);
 std::cout<<"causal RAM exclusion, hit parity, value symmetry, bounded state, clock semantics and H isolation passed\n";
}
