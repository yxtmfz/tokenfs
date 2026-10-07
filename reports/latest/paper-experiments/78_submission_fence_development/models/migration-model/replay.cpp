#include "measured_policy.h"
#include <iostream>
#include <fstream>
#include <list>
#include <map>
#include <set>
#include <iomanip>
using namespace tokenfs_policy;
int main(int argc,char**argv){
 if(argc<4)return 2;
 const std::string mode=argv[2];const int capacity=4;
 diagnostic_conditional_prior=mode=="conditional_ram";
 diagnostic_censored_cohort=mode=="censored"||mode=="common_ram_censored";
 diagnostic_cost_bootstrap=mode=="common_ram_bootstrap"||mode=="bootstrap";
 std::ofstream log(argv[3]);
 log<<"arm\tobservation\taction\tkey\tlocation\treason\tincoming_us\tloss_us\tcopy_us\tcohort\tvictims\n";
 for(std::string arm:{"Full","NoHotspot","NoAffinity","NoJoint"}){
  MeasuredPolicy policy;Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;
  o.object_weighted_cohort_prior=true;o.disk_opportunity_value=false;o.recent_value_floor=true;o.cohort_reuse_prior=true;o.static_reuse_value=arm=="NoHotspot";o.joint_admission=arm!="NoJoint";
  constexpr uint64_t size=2097152;policy.ReadSample(false,size,21000);policy.ReadSample(true,size,10500);policy.CopySample(size,8000);
  std::map<int,std::map<std::string,int>> caches;std::list<std::string> ram;
  std::ifstream in(argv[1]);std::string key;int caller,i=0,remote=0,copies=0,ram_hits=0,disk_hits=0,replans=0;
  std::map<std::string,int> lastcaller;std::set<std::string> seen;int compulsory=0;
  auto place=[&](const std::string& target,int owner,const std::string& action){
   for(const auto&[g,c]:caches)if(c.count(target))return;
   ++replans;int selected=-1;double best=0;Decision chosen;
   for(int g:{owner,(owner+1)%3,(owner+2)%3}){
    if(arm=="NoAffinity"&&g!=owner)continue;
    std::vector<Item> residents;for(auto&[k,at]:caches[g])residents.push_back({k,size,uint64_t(at),1.0});
    auto d=policy.Plan(g,{target,size,0},residents,caches[g].size()*size,capacity*size,o);
    double net=d.incoming_us-d.copy_us-(o.joint_admission?d.displaced_us+d.uncertainty_us:0);
    if(d.allowed && d.explore_headroom){selected=g;chosen=d;break;}
    if(d.allowed && net>best){selected=g;chosen=d;best=net;}
    if(d.allowed && (!o.joint_admission||d.displaced_us+d.uncertainty_us==0))break;
   }
   if(selected>=0){
    log<<arm<<'\t'<<i<<'\t'<<action<<'\t'<<target<<'\t'<<selected<<'\t'<<chosen.reason<<'\t'<<chosen.incoming_us<<'\t'<<chosen.displaced_us<<'\t'<<chosen.copy_us<<'\t'<<chosen.cohort_disk_reuse<<'\t';
    for(auto&v:chosen.victims){log<<v<<',';caches[selected].erase(v);}log<<'\n';
    caches[selected][target]=i;++copies;
   }
  };
  while(in>>key>>caller){++i;bool local=false;for(auto&[g,c]:caches)if(c.count(key)){local=true;c[key]=i;}
   bool captured=std::find(ram.begin(),ram.end(),key)!=ram.end();diagnostic_ram_hit=captured;policy.Observe(caller,key,o,local||captured);lastcaller[key]=caller;
   if(captured)++ram_hits;else if(local)++disk_hits;else{++remote;if(!seen.count(key))++compulsory;log<<arm<<'\t'<<i<<"\tremote\t"<<key<<'\t'<<caller<<"\t\t0\t0\t0\t0\t\n";}
   seen.insert(key);ram.remove(key);ram.push_back(key);
   std::string spill;if(ram.size()>2){spill=ram.front();ram.pop_front();}
   if(mode=="spill"&&!o.static_reuse_value){if(!spill.empty())place(spill,lastcaller[spill],"spill");}
   else if(!captured&&!local)place(key,caller,"remote_admit");
   else if(captured&&!local&&(!o.static_reuse_value||(mode=="common_ram"||mode=="common_ram_bootstrap"||mode=="common_ram_censored"))&&(mode=="conditional_ram"||mode=="original_ram"||mode=="common_ram"||mode=="common_ram_bootstrap"||mode=="common_ram_censored"))place(key,caller,"ram_admit");
  }
  std::cout<<arm<<" remote="<<remote<<" copies="<<copies<<" ram_hits="<<ram_hits<<" disk_hits="<<disk_hits<<" requests="<<i<<" plans="<<replans<<" compulsory="<<compulsory<<'\n';
 }
}
