#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main() {
  {
    RunReuse summary;uint64_t at=0;
    auto run=[&](const std::string& k,int n){for(int i=0;i<n;++i)summary.Observe(k,++at,128);};
    run("old",4);run("x",4);run("old",4);
    const double initial=summary.CompetitionSurvival("old");assert(initial==1);
    for(int i=0;i<12;++i)run("scan"+std::to_string(i),4);
    assert(summary.CompetitionSurvival("old")==initial); // A scan is not a new working set.
    run("new",4);run("separator",4);run("new",4);
    assert(summary.CompetitionSurvival("old")==.5 && summary.CompetitionSurvival("new")==1);
    run("new",4);assert(summary.CompetitionSurvival("old")==.5); // censored active burst
    run("old",4);assert(summary.CompetitionSurvival("old")==1); // renewed demand restores evidence
  }

  {
    Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;
    o.persistent_run_reuse=true;o.persistent_reuse_immediate_decay=true;o.admission=false;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
    auto run=[&](const std::string& k){for(int i=0;i<4;++i)p.Observe(0,k,o);};
    run("old");run("separator0");run("old");run("new");run("separator1");run("new");
    auto loss=[&](Options x){return p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,x).displaced_us;};
    auto novel=o;novel.novel_reuse_decay=true;
    assert(loss(novel)==.5*loss(o) && loss(o)>0);
    auto same=p.Plan(0,{"new",100,0},{{"new",100,0}},100,100,novel);
    assert(same.incoming_us==same.displaced_us);
  }
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
  Options no_h=o;no_h.static_reuse_value=true;
  assert(loss(no_h)==0); // Static recent frequency forgets expired requests.
  const auto symmetric=p.Plan(0,{"hot",100,0},{{"hot",100,0}},100,100,o);
  assert(symmetric.incoming_us==symmetric.displaced_us && symmetric.persistent_reuse_adjusted_items==2);
  Options faster=o;faster.persistent_reuse_immediate_decay=true;
  assert(loss(faster)>0 && loss(faster)<loss(o));
  const auto before=loss(o);obs("moving",128);assert(loss(o)<before);
  assert(p.Plan(0,{"moving",100,0},{{"hot",100,0}},100,100,o).allowed);
  const auto static_plan=p.Plan(0,{"moving",100,0},{{"hot",100,0}},100,100,no_h);
  assert(static_plan.allowed && static_plan.incoming_us==127*80 && static_plan.displaced_us==0);
  assert(!p.Plan(0,{"oversize",101,0},{},0,100,o).allowed);
  assert(!p.Plan(0,{"moving",100,0},{},100,100,o).allowed); // no evictable capacity
  std::cout<<"persistent recurrence, censored runs, decay, bounds and symmetric value passed\n";
}
