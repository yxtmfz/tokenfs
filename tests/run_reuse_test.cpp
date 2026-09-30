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
    o.persistent_run_reuse=true;o.persistent_reuse_immediate_decay=true;o.admission=false;o.adaptive_control=true;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
    auto run=[&](const std::string& k){for(int i=0;i<4;++i)p.Observe(0,k,o);};
    run("old");run("separator0");run("old");run("new");run("separator1");run("new");
    auto loss=[&](Options x){return p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,x).displaced_us;};
    auto novel=o;novel.novel_reuse_decay=true;
    assert(loss(novel)==.5*loss(o) && loss(o)>0);
    auto floor=novel;floor.recent_value_floor=true;
    auto observed=o;observed.persistent_run_reuse=false;
    assert(loss(floor)>=loss(observed) && loss(floor)>loss(novel));
    auto symmetric_floor=p.Plan(0,{"new",100,0},{{"new",100,0}},100,100,floor);
    assert(symmetric_floor.incoming_us==symmetric_floor.displaced_us);

    auto same=p.Plan(0,{"new",100,0},{{"new",100,0}},100,100,novel);
    assert(same.incoming_us==same.displaced_us);
  }
  {
    Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;
    o.persistent_run_reuse=true;o.adaptive_control=true;o.admission=false;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
    // Repeated but interleaved keys have no adjacent clustering. New recurrence
    // must not erase established resident evidence just because it is new.
    for(int i=0;i<20;++i)p.Observe(0,i%2?"old":"separator",o);
    p.Observe(0,"new",o);p.Observe(0,"separator",o);p.Observe(0,"new",o);
    auto loss=[&](Options x){return p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,x).displaced_us;};
    auto novel=o;novel.novel_reuse_decay=true;
    assert(loss(o)>0 && loss(novel)==loss(o));
  }
  {
    Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;o.admission=false;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
    for(int i=0;i<49;++i)p.Observe(0,(i/4)%2?"a":"b",o);
    auto memory=o;memory.retained_capture=true;
    auto raw=p.Plan(0,{"b",100,0},{},0,100,o);
    auto marginal=p.Plan(0,{"b",100,0},{},0,100,memory);
    assert(raw.burst_remaining>0 && marginal.burst_remaining==0);
    assert(marginal.incoming_us==raw.incoming_us/4); // completed four-read runs
    memory.static_reuse_value=true;
    auto symmetric=p.Plan(0,{"a",100,0},{{"a",100,0}},100,100,memory);
    assert(symmetric.incoming_us==symmetric.displaced_us);
  }
  {
    Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;o.shift_reset=true;
    o.persistent_run_reuse=true;o.adaptive_control=true;o.retained_capture=true;o.cohort_reuse_prior=true;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,10);
    p.Observe(0,"first",o);assert(p.Plan(0,{"first",100,0},{},0,100,o).cohort_disk_reuse==0);
    for(int i=0;i<64;++i)p.Observe(0,(i/4)%2?"a":"b",o);
    p.Observe(0,"new",o);
    const auto prior=p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,o);
    assert(prior.allowed && prior.cohort_disk_reuse>0 && prior.cohort_disk_reuse<=1);
    auto no_h=o;no_h.static_reuse_value=true;
    assert(!p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,no_h).allowed);
    auto same=p.Plan(0,{"new",100,0},{{"new",100,0}},100,100,o);
    assert(same.incoming_us==same.displaced_us && !same.allowed);
    p.CopySample(100,10000);
    assert(!p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,o).allowed);
    MeasuredPolicy iid;
    for(int i=0;i<128;++i)iid.Observe(0,i%2?"a":"b",o);
    iid.Observe(0,"new",o);
    assert(iid.Plan(0,{"new",100,0},{},0,100,o).cohort_disk_reuse==0);
    RunReuse r;for(int i=0;i<40;++i)r.Observe("scan"+std::to_string(i),i+1,128);
    assert(r.NewcomerDiskPrior("scan39")==0);
  }
  {
    RunReuse r;uint64_t at=0;
    auto observe=[&](const std::string& k,int n){for(int i=0;i<n;++i)r.Observe(k,++at,128);};
    observe("a",4);observe("b",28);observe("a",4);observe("b",28);
    const auto last_return=at-27; // start of the second b run, not its RAM repeats
    observe("new",4);
    assert(r.NewcomerDiskPrior("new")>0);
    assert(std::abs(r.NewcomerSurvival("new",at)-std::exp2(-double(at-last_return)/32.0))<1e-12);
    observe("scan",12);
    // Use observed between-run spacing, but age the borrowed evidence too.
    // New objects cannot turn an old cohort observation into a fresh forecast.
    assert(std::abs(r.NewcomerSurvival("new",at)-std::exp2(-double(at-last_return)/32.0))<1e-12);
    assert(r.NewcomerSurvival("new",at)>std::exp2(-double(at-last_return)/4.0));
    const auto before=r.NewcomerSurvival("new",at);observe("scan",128);
    assert(r.NewcomerSurvival("new",at)<before);
    assert(r.NewcomerSurvival("missing",at)==0);
    observe("new",4);assert(r.NewcomerDiskPrior("new")==0); // own evidence takes over
  }
  {
    RunReuse r;uint64_t at=0;
    auto run=[&](const std::string& key,int n){for(int i=0;i<n;++i)r.Observe(key,++at,128);};
    run("hot",4);run("other",4);run("hot",4);run("new0",4);
    const auto first=r.NewcomerSurvival("new0",at);
    run("new1",4);const auto scan=r.NewcomerSurvival("new1",at);
    assert(scan>0 && scan<first); // Fresh key, stale cohort evidence.
    run("new1",32);const auto adjacent=r.NewcomerSurvival("new1",at);
    assert(adjacent<scan); // Adjacent repeats cannot assert a distinct return.
    run("hot",4);run("new2",1);
    assert(r.NewcomerSurvival("new2",at)>adjacent); // A real return renews evidence.
    assert(r.NewcomerDiskPrior("hot")==0); // Established keys use their own evidence.
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
  r.Observe("last",++t,2);assert(r.Entries()<=2 && r.Runs()<=2 && r.ReturnIntervals()<=2);

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
