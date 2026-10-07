#include "measured_policy.h"
#include <iostream>
#include <fstream>
#include <list>
#include <map>
using namespace tokenfs_policy;
int main(int argc,char**argv){
 for(std::string arm:{"Full","NoHotspot","NoAffinity","NoJoint"}){
  MeasuredPolicy policy;Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;
  o.recent_value_floor=true;o.cohort_reuse_prior=true;o.static_reuse_value=arm=="NoHotspot";o.joint_admission=arm!="NoJoint";
  constexpr uint64_t size=2097152;policy.ReadSample(false,size,21000);policy.ReadSample(true,size,10500);policy.CopySample(size,8000);
  std::map<int,std::map<std::string,int>> caches;std::list<std::string> ram;std::map<std::string,int> callers;
  std::ifstream in(argv[1]);std::string key;int caller,i=0,remote=0,copies=0;
  auto admit=[&](const std::string& k,int c){
   for(auto& [g,cache]:caches)if(cache.count(k))return;
   int selected=-1;double best=0;Decision chosen;
   for(int g:{c,(c+1)%3,(c+2)%3}){
    if(arm=="NoAffinity"&&g!=c)continue;
    std::vector<Item> residents;for(auto&[v,at]:caches[g])residents.push_back({v,size,uint64_t(at),1.0});
    auto d=policy.Plan(g,{k,size,0},residents,caches[g].size()*size,4*size,o);
    double net=d.incoming_us-d.copy_us-(o.joint_admission?d.displaced_us+d.uncertainty_us:0);
    if(d.allowed && d.explore_headroom){selected=g;chosen=d;break;}
    if(d.allowed && net>best){selected=g;chosen=d;best=net;}
    if(d.allowed && (!o.joint_admission||d.displaced_us+d.uncertainty_us==0))break;
   }
   if(selected>=0){for(auto&v:chosen.victims)caches[selected].erase(v);caches[selected][k]=i;++copies;}
  };
  while(in>>key>>caller){++i;bool local=false;for(auto& [g,c]:caches)if(c.count(key)){local=true;c[key]=i;}
   bool captured=std::find(ram.begin(),ram.end(),key)!=ram.end();policy.Observe(caller,key,o,local||captured);
   ram.remove(key);ram.push_back(key);callers[key]=caller;
   if(ram.size()>2){const auto retired=ram.front();ram.pop_front();if(!o.static_reuse_value)admit(retired,callers.at(retired));callers.erase(retired);}
   if(captured||local)continue;++remote;
   if(o.static_reuse_value)admit(key,caller);
  }
  std::cout<<arm<<" remote="<<remote<<" copies="<<copies<<"\n";
 }
}
