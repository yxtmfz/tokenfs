#include "measured_policy.h"
#include <iostream>
#include <fstream>
#include <list>
#include <map>
using namespace tokenfs_policy;
int main(int argc,char**argv){
 for(std::string arm:{"Full","NoHotspot","NoAffinity","NoJoint"}){
  MeasuredPolicy policy;Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;
  o.disk_opportunity_value=true;o.recent_value_floor=true;o.cohort_reuse_prior=argc>2;o.static_reuse_value=arm=="NoHotspot";o.joint_admission=arm!="NoJoint";
  constexpr uint64_t size=2097152;policy.ReadSample(false,size,21000);policy.ReadSample(true,size,10500);policy.CopySample(size,8000);
  std::map<int,std::map<std::string,int>> caches;std::list<std::string> ram;
  std::ifstream in(argv[1]);std::string key;int caller,i=0,remote=0,copies=0,ramhits=0,diskhits=0,headroom_copies=0;std::map<std::string,int> reasons;
  while(in>>key>>caller){++i;bool local=false;for(auto& [g,c]:caches)if(c.count(key)){local=true;c[key]=i;}
   bool captured=std::find(ram.begin(),ram.end(),key)!=ram.end();policy.Observe(caller,key,o,local||captured);
   if(captured)++ramhits;else if(local)++diskhits;
   ram.remove(key);ram.push_back(key);if(ram.size()>2)ram.pop_front();
   if(captured||local)continue;++remote;
   int selected=-1;double best=0;Decision chosen;
   if(false)std::cerr<<i<<" "<<key<<" miss\n";
   for(int g:{caller,(caller+1)%3,(caller+2)%3}){
    if(arm=="NoAffinity"&&g!=caller)continue;
    std::vector<Item> residents;for(auto&[k,at]:caches[g])residents.push_back({k,size,uint64_t(at),1.0});
    auto d=policy.Plan(g,{key,size,0},residents,caches[g].size()*size,4*size,o);
    double net=d.incoming_us-d.copy_us-(o.joint_admission?d.displaced_us+d.uncertainty_us:0);
    if(d.allowed && d.explore_headroom){selected=g;chosen=d;break;}
    if(d.allowed && net>best){selected=g;chosen=d;best=net;}
    if(d.allowed && (!o.joint_admission||d.displaced_us+d.uncertainty_us==0))break;
    ++reasons[d.reason];
   }
   if(selected>=0){headroom_copies+=chosen.explore_headroom;for(auto&v:chosen.victims){if(false)std::cerr<<i<<" "<<key<<" evict "<<v<<" gain "<<chosen.incoming_us<<" loss "<<chosen.displaced_us<<" copy "<<chosen.copy_us<<"\n";caches[selected].erase(v);}caches[selected][key]=i;++copies;}
  }
  std::cout<<arm<<" remote="<<remote<<" copies="<<copies<<" ram_hits="<<ramhits<<" disk_hits="<<diskhits<<" requests="<<i<<" headroom_copies="<<headroom_copies;for(auto&[r,n]:reasons)std::cout<<" "<<r<<"="<<n;std::cout<<policy.CalibrationStats()<<"\n";
 }
}
