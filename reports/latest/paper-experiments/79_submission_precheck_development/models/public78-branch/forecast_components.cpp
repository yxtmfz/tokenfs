#include "measured_policy.h"
#include <fstream>
#include <iostream>
#include <iomanip>
using namespace tokenfs_policy;
int main(int argc,char**argv){
 if(argc!=2)return 2;
 MeasuredPolicy policy;Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;
 o.object_weighted_cohort_prior=true;o.recent_value_floor=true;o.cohort_reuse_prior=true;
 constexpr uint64_t size=2097152;
 // Artificial unit rates only isolate dimensionless forecast and uncertainty.
 // This is not latency evidence: one object has SavingRate*bytes exactly 1 us.
 policy.ReadSample(false,size,2);policy.ReadSample(true,size,1);policy.CopySample(size,1);
 std::ifstream in(argv[1]);std::string key;int caller;uint64_t observation=0;
 std::cout<<std::setprecision(12);
 while(in>>key>>caller){++observation;policy.Observe(caller,key,o,false);
  if(observation>=60 && observation<=64)for(const auto& target:{"45","46"}){
   auto d=policy.Plan(1,{target,size,0},{{"4",size,5,1.0}},size,size,o);
   std::cout<<"observation="<<observation<<" key="<<target<<" forecast="<<d.incoming_us<<" uncertainty_factor="<<d.uncertainty_us<<" shared_count="<<d.affinity_incoming_count<<" victim_value="<<d.displaced_us<<" cohort="<<d.cohort_disk_reuse<<"\n";
  }
 }
}
