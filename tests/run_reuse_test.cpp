#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main() {
  RunReuse r;uint64_t t=0;
  auto run=[&](const std::string& k,int n){for(int i=0;i<n;++i)r.Observe(k,++t,128);};
  run("hot",4);run("a",28);run("hot",4);run("b",28);run("hot",4);
  const double known=r.Estimate("hot",t,128);
  assert(known>0);
  // Current run is censored: extending it cannot inflate learned run length.
  run("hot",20);assert(r.Estimate("hot",t,128)==known);
  run("c",140);assert(r.Estimate("hot",t,128)>0); // survives request-window expiry
  assert(r.Estimate("c",t,128)==0); // one burst is not recurring reuse
  const double aged=r.Estimate("hot",t,128);
  assert(r.Estimate("hot",t,128,true)<aged);
  run("c",140);assert(r.Estimate("hot",t,128)<aged);
  for(int i=0;i<200;++i)run("scan"+std::to_string(i),1);
  assert(r.Entries()<=128 && r.Runs()<=128 && r.Estimate("hot",t,128)==0);
  r.Observe("last",++t,2);assert(r.Entries()<=2 && r.Runs()<=2);

  Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;
  o.burst_interval_survival=true;o.persistent_run_reuse=true;o.admission=false;
  MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
  auto obs=[&](const std::string& k,int n){for(int i=0;i<n;++i)p.Observe(i%3,k,o);};
  for(int j=0;j<6;++j){obs("hot",4);obs("other"+std::to_string(j),28);}
  obs("scan",140);
  Options old=o;old.persistent_run_reuse=false;
  auto loss=[&](const Options& x){return p.Plan(0,{"new",100,0},{{"hot",100,0}},100,100,x).displaced_us;};
  assert(loss(old)==0 && loss(o)>0);
  const auto symmetric=p.Plan(0,{"hot",100,0},{{"hot",100,0}},100,100,o);
  assert(symmetric.incoming_us==symmetric.displaced_us && symmetric.persistent_reuse_adjusted_items==2);
  Options faster=o;faster.persistent_reuse_immediate_decay=true;
  assert(loss(faster)>0 && loss(faster)<loss(o));
  const auto before=loss(o);obs("moving",128);assert(loss(o)<before);
  assert(p.Plan(0,{"moving",100,0},{{"hot",100,0}},100,100,o).allowed);
  assert(!p.Plan(0,{"oversize",101,0},{},0,100,o).allowed);
  assert(!p.Plan(0,{"moving",100,0},{},100,100,o).allowed); // no evictable capacity
  std::cout<<"persistent recurrence, censored runs, decay, bounds and symmetric value passed\n";
}
