#include "../src/measured_policy.h"
#include <cassert>
#include <cmath>
#include <iostream>
using namespace tokenfs_policy;
int main(){
 RunReuse r;
 for(uint64_t i=1;i<=4;++i)r.Observe("a",i,128);
 assert(r.DiskOpportunity("a",4,128)==0); // one RAM burst is not recurrence
 for(uint64_t i=5;i<17;++i)r.Observe("other",i,128);
 r.Observe("a",17,128);
 const auto first=r.DiskOpportunity("a",17,128);
 assert(first==4.0); // horizon 128 / completed gap 16 * confidence 1/2
 assert(r.DiskOpportunity("a",33,128)==first); // do not expire before expected return
 assert(r.DiskOpportunity("a",49,128)==first/2); // stale recurrence still expires
 for(uint64_t i=18;i<=20;++i)r.Observe("a",i,128);
 assert(r.DiskOpportunity("a",20,128)==first); // adjacent reads add no disk opportunities
 for(uint64_t i=21;i<200;++i)r.Observe("unique"+std::to_string(i),i,8);
 assert(r.Entries()<=8 && r.DiskOpportunity("a",200,128)==0);
 Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=true;
 o.retained_capture=o.persistent_run_reuse=o.disk_opportunity_value=o.cohort_reuse_prior=true;
 o.shift_reset=o.efficient_planning=o.recent_value_floor=true;
 MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
 for(int i=0;i<96;++i)p.Observe(i%3,"k"+std::to_string(i/4%4),o);
 auto same=p.Plan(0,{"k0",100,0},{{"k0",100,0}},100,100,o);
 assert(same.incoming_us==same.displaced_us && !same.allowed);
 p.Observe(0,"new",o);
 auto newcomer=p.Plan(0,{"new",100,0},{{"k0",100,0}},100,100,o);
 assert(newcomer.cohort_disk_reuse==0 && !newcomer.allowed);
 Options no=o;no.static_reuse_value=true;Options old=no;old.disk_opportunity_value=false;
 for(int i=0;i<160;++i){
  auto key="k"+std::to_string(i%7);p.Observe(i%3,key,no);
  auto a=p.Plan(i%3,{key,100,0},{{"k1",100,0}},100,100,no);
  auto b=p.Plan(i%3,{key,100,0},{{"k1",100,0}},100,100,old);
  assert(a.allowed==b.allowed && a.victims==b.victims && a.reason==b.reason);
  assert(a.incoming_us==b.incoming_us && a.displaced_us==b.displaced_us && a.uncertainty_us==b.uncertainty_us);
  assert(a.copy_us==b.copy_us && a.persistent_reuse_adjusted_items==b.persistent_reuse_adjusted_items);
  assert(p.PotentiallyProfitable(i%3,{key,100,0},100,100,no)||!a.allowed);
  assert(p.PotentiallyProfitable(i%3,{key,100,0},100,100,o)||!p.Plan(i%3,{key,100,0},{{"k1",100,0}},100,100,o).allowed);
 }
 std::cout<<"disk opportunity causality, expiry, symmetry and ablation passed\n";
}
