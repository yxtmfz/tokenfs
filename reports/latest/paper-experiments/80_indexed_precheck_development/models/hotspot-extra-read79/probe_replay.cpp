#include "measured_policy.h"
#include <iostream>
#include <fstream>
#include <list>
#include <map>
#include <iomanip>
using namespace tokenfs_policy;
int main(int argc,char**argv){
 std::ofstream probes(argv[4]);probes<<"arm\tobservation\tkey\tmoment\tdomain\tallowed\treason\tfrequency\tincoming\tdisplaced\tuncertainty\tcopy\tcohort\tvictims\n";probes<<std::setprecision(17);
 std::ofstream eventlog(argc>3?argv[3]:"/dev/null");eventlog<<"kind\tarm\tobservation\tkey\tdetail\n";
 const int capacity=4; const bool rank_ram=argc>2 && std::string(argv[2])!="lru";
 if(capacity<1)return 2; const bool marginal_ram=argc>2 && std::string(argv[2])=="marginal";
 for(std::string arm:{"Full","NoHotspot"}){
  MeasuredPolicy policy;Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;
  o.object_weighted_cohort_prior=true;o.disk_opportunity_value=false;o.recent_value_floor=true;o.cohort_reuse_prior=argc>2;o.static_reuse_value=arm=="NoHotspot";o.joint_admission=arm!="NoJoint";
  constexpr uint64_t size=2097152;policy.ReadSample(false,size,21000);policy.ReadSample(true,size,10500);policy.CopySample(size,8000);
  std::map<int,std::map<std::string,int>> caches;std::list<std::string> ram;std::map<std::string,int> ram_recency;int ram_rank_evictions=0;
  std::ifstream in(argv[1]);std::string key;int caller,i=0,remote=0,copies=0,ram_hits=0,disk_hits=0;std::map<std::string,int> reasons;
  while(in>>key>>caller){++i;bool local=false;for(auto& [g,c]:caches)if(c.count(key)){local=true;c[key]=i;}
   bool captured=std::find(ram.begin(),ram.end(),key)!=ram.end();policy.Observe(caller,key,o,local||captured);
   eventlog<<"request\t"<<arm<<'\t'<<i<<'\t'<<key<<'\t'<<captured<<":"<<local<<'\n';
   auto probe=[&](const std::string& target,const char* moment) {
    for(const auto& [g,c]:caches)if(c.count(target))return;
    for(int g:{caller,(caller+1)%3,(caller+2)%3}) {
      std::vector<Item> residents;for(const auto& [k,at]:caches[g])residents.push_back({k,size,uint64_t(at),1.0});
      auto d=policy.Plan(g,{target,size,0},residents,caches[g].size()*size,capacity*size,o);
      probes<<arm<<'\t'<<i<<'\t'<<target<<'\t'<<moment<<'\t'<<g<<'\t'<<d.allowed<<'\t'<<d.reason<<'\t'<<d.affinity_incoming_count<<'\t'<<d.incoming_us<<'\t'<<d.displaced_us<<'\t'<<d.uncertainty_us<<'\t'<<d.copy_us<<'\t'<<d.cohort_disk_reuse<<'\t';
      for(const auto& victim:d.victims)probes<<victim<<',';probes<<'\n';
    }
   };
   probe(key,"current_observed");
   ram.remove(key);ram.push_back(key);ram_recency[key]=i;
   if(ram.size()>2) {probe(ram.front(),"RAM_eviction");
    if(rank_ram) {
      std::vector<Item> candidates;for(const auto& k:ram)if(k!=key) {
        bool on_disk=false;for(const auto& [g,c]:caches)if(c.count(k))on_disk=true;
        // The fixed model serves remote in21ms and local in10.5ms; RAM0.
        // Thus a remote-only RAM copy saves twice the service of a disk-backed one.
        const double coverage=marginal_ram && !on_disk?2.0:1.0;
        candidates.push_back({k,size,uint64_t(ram_recency[k]),coverage});
      }
      const auto ranked=policy.Ranked(caller,std::move(candidates),o);if(ranked.empty())return 3;
      eventlog<<"ram_evict\t"<<arm<<'\t'<<i<<'\t'<<ranked.front().key<<"\tvalue\n";
      ram.remove(ranked.front().key);ram_recency.erase(ranked.front().key);++ram_rank_evictions;
    } else {eventlog<<"ram_evict\t"<<arm<<'\t'<<i<<'\t'<<ram.front()<<"\tlru\n";ram_recency.erase(ram.front());ram.pop_front();}
   }
   if(ram.size()>2 || std::find(ram.begin(),ram.end(),key)==ram.end())return 4;
   if(captured)++ram_hits;else if(local)++disk_hits;
   if(captured||local)continue;++remote;
   int selected=-1;double best=0;Decision chosen;
   if(false)std::cerr<<i<<" "<<key<<" miss\n";
   for(int g:{caller,(caller+1)%3,(caller+2)%3}){
    if(arm=="NoAffinity"&&g!=caller)continue;
    std::vector<Item> residents;for(auto&[k,at]:caches[g])residents.push_back({k,size,uint64_t(at),1.0});
    auto d=policy.Plan(g,{key,size,0},residents,caches[g].size()*size,capacity*size,o);
    double net=d.incoming_us-d.copy_us-(o.joint_admission?d.displaced_us+d.uncertainty_us:0);
    if(d.allowed && d.explore_headroom){selected=g;chosen=d;break;}
    if(d.allowed && net>best){selected=g;chosen=d;best=net;}
    if(d.allowed && (!o.joint_admission||d.displaced_us+d.uncertainty_us==0))break;
    ++reasons[d.reason];
   }
   if(selected>=0){eventlog<<"copy\t"<<arm<<'\t'<<i<<'\t'<<key<<'\t'<<selected;for(const auto& victim:chosen.victims)eventlog<<":"<<victim;eventlog<<'\n';for(auto&v:chosen.victims){if(false)std::cerr<<i<<" "<<key<<" evict "<<v<<" gain "<<chosen.incoming_us<<" loss "<<chosen.displaced_us<<" copy "<<chosen.copy_us<<"\n";caches[selected].erase(v);}caches[selected][key]=i;++copies;}
  }
  std::cout<<arm<<" remote="<<remote<<" copies="<<copies<<" ram_hits="<<ram_hits<<" disk_hits="<<disk_hits<<" requests="<<i<<" ram_rank_evictions="<<ram_rank_evictions;for(auto&[r,n]:reasons)std::cout<<" "<<r<<"="<<n;std::cout<<"\n";
 }
}
