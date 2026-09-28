#include "../src/measured_policy.h"
#include <cassert>
#include <random>
using namespace tokenfs_policy;
void equal(const Decision& a,const Decision& b) {
 assert(a.allowed==b.allowed && a.reason==b.reason && a.victims==b.victims);
 assert(a.incoming_us==b.incoming_us && a.displaced_us==b.displaced_us && a.copy_us==b.copy_us);
 assert(a.uncertainty_us==b.uncertainty_us && a.burst_remaining==b.burst_remaining);
 assert(a.incoming_count==b.incoming_count && a.affinity_incoming_count==b.affinity_incoming_count);
 assert(a.affinity_adjusted_items==b.affinity_adjusted_items && a.survival_adjusted_items==b.survival_adjusted_items);
 assert(a.costs_calibrated==b.costs_calibrated && a.explore_headroom==b.explore_headroom);
}
int main(){
 std::mt19937 rng(73529);
 for(bool joint:{false,true})for(bool shared:{false,true})for(int window:{2,8,128}) {
  MeasuredPolicy reference,fast;Options a;a.window=window;a.causal_window=true;a.shared_value=shared;
  a.burst_reuse=shared;a.adaptive_control=true;a.shift_reset=true;a.joint_admission=joint;
  Options b=a;b.efficient_planning=true;
  for(int i=0;i<1000;++i) {
   // Changing windows, repeated runs, singletons, and randomly interleaved keys.
   if(i==300)a.window=b.window=32;
   if(i==700)a.window=b.window=3;
   const int node=rng()%3;const auto key="k"+std::to_string(i%3?i/4%11:rng()%17);
   assert(reference.Observe(node,key,a,i%2)==fast.Observe(node,key,b,i%2));
   if(i%9==0) {
    uint64_t local=1+rng()%80,remote=100+rng()%200,copy=20+rng()%400;
    reference.ReadSample(true,100,local);fast.ReadSample(true,100,local);
    reference.ReadSample(false,100,remote);fast.ReadSample(false,100,remote);
    reference.CopySample(100,copy);fast.CopySample(100,copy);
   }
   std::vector<Item> residents;
   for(int n=0;n<7;++n)residents.push_back({"k"+std::to_string(n),uint64_t(10+n*7),uint64_t(n%2),n%3?1.0:0.0});
   a.value_victim=b.value_victim=i%7!=0;a.size_aware=b.size_aware=i%5!=0;
   a.cost=b.cost=i%11!=0;
   equal(reference.Plan(node,{key,uint64_t(10+i%60),0},residents,217,240,a),fast.Plan(node,{key,uint64_t(10+i%60),0},residents,217,240,b));
   auto x=reference.Ranked(node,residents,a),y=fast.Ranked(node,residents,b);
   assert(x.size()==y.size());for(size_t j=0;j<x.size();++j)assert(x[j].key==y[j].key);
  }
 }
}
