#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main() {
  {
    RunReuse brief,repeated;uint64_t at=0;
    for(int i=0;i<2;++i){brief.Observe("a",++at,128);brief.Observe("b",++at,128);}
    brief.Observe("new",++at,128);
    at=0;for(int i=0;i<50;++i){repeated.Observe("a",++at,128);repeated.Observe("b",++at,128);}
    repeated.Observe("new",++at,128);
    // Repeated returns by the same two objects are two supporting objects,
    // not ninety-eight independent pieces of newcomer-return evidence.
    assert(brief.NewcomerDiskPrior("new",true)==.5);
    assert(repeated.NewcomerDiskPrior("new",true)==.5);
    assert(brief.NewcomerDiskPrior("new")==.5 && repeated.NewcomerDiskPrior("new")==1);
    assert(repeated.RecurrentEntries()==2);
    const auto before=repeated.NewcomerDiskPrior("new",true);
    for(int i=0;i<80;++i)repeated.Observe("new",++at,128);
    assert(repeated.NewcomerDiskPrior("new",true)==before); // unfinished run adds no evidence
    assert(repeated.NewcomerDiskPrior("not-yet-seen",true)==0);
    repeated.Observe("a",++at,128);repeated.Observe("new",++at,128);
    assert(repeated.NewcomerDiskPrior("new",true)==0 && repeated.RecurrentEntries()==3);
    for(int i=0;i<140;++i)repeated.Observe("cold"+std::to_string(i),++at,128);
    assert(repeated.Entries()<=128 && repeated.RecurrentEntries()==0);
    assert(repeated.NewcomerDiskPrior("cold139",true)==0);
    repeated.Observe("hot",++at,128);repeated.Observe("between",++at,128);repeated.Observe("hot",++at,128);
    assert(repeated.RecurrentEntries()==1);
    repeated.Observe("x",++at,2);repeated.Observe("y",++at,2);
    assert(repeated.Entries()==2 && repeated.RecurrentEntries()==0 && repeated.Runs()==2);
  }
  {
    RunReuse single_hot;uint64_t at=0;double previous=1;
    for(int i=0;i<40;++i) {
      single_hot.Observe("hot",++at,128);
      const auto cold="one-off"+std::to_string(i);single_hot.Observe(cold,++at,128);
      const double support=single_hot.NewcomerDiskPrior(cold,true);
      if(i>0) {
        assert(single_hot.RecurrentEntries()==1 && support<=previous);
        assert(support==1.0/(single_hot.Entries()+1.0));
      }
      if(i>0)previous=support;
      assert(support>=0 && support<1);
    }
  }
  {
    Options o;o.causal_window=o.shared_value=o.burst_reuse=o.shift_reset=true;
    o.persistent_run_reuse=o.adaptive_control=o.retained_capture=o.cohort_reuse_prior=true;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,10);
    for(int i=0;i<64;++i)p.Observe(i%3,(i/4)%2?"a":"b",o);
    p.Observe(0,"new",o);
    auto object=o;object.object_weighted_cohort_prior=true;
    auto plan=[&](Options x){return p.Plan(0,{"new",100,0},{{"old",100,0}},100,100,x);};
    const auto old=plan(o),weighted=plan(object);
    assert(weighted.cohort_disk_reuse>0 && weighted.cohort_disk_reuse<old.cohort_disk_reuse);
    assert(weighted.incoming_us<old.incoming_us && weighted.copy_us==old.copy_us);
    const auto symmetric=p.Plan(0,{"new",100,0},{{"new",100,0}},100,100,object);
    assert(symmetric.incoming_us==symmetric.displaced_us && !symmetric.allowed);
    for(bool disk_opportunity:{false,true})for(bool joint:{false,true}) {
      auto legacy=o,candidate=object;
      legacy.static_reuse_value=candidate.static_reuse_value=true;
      legacy.disk_opportunity_value=candidate.disk_opportunity_value=disk_opportunity;
      legacy.joint_admission=candidate.joint_admission=joint;
      const auto a=plan(legacy),b=plan(candidate);
      assert(a.allowed==b.allowed && a.reason==b.reason && a.victims==b.victims);
      assert(a.incoming_us==b.incoming_us && a.displaced_us==b.displaced_us);
      assert(a.copy_us==b.copy_us && a.uncertainty_us==b.uncertainty_us && b.cohort_disk_reuse==0);
    }
    auto no_cohort=o;no_cohort.cohort_reuse_prior=false;
    auto no_cohort_object=no_cohort;no_cohort_object.object_weighted_cohort_prior=true;
    assert(plan(no_cohort).incoming_us==plan(no_cohort_object).incoming_us);
    auto disk=o;disk.disk_opportunity_value=true;
    auto disk_object=disk;disk_object.object_weighted_cohort_prior=true;
    assert(plan(disk).incoming_us==plan(disk_object).incoming_us && plan(disk_object).cohort_disk_reuse==0);
  }
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
    observe("a",4);observe("b",28);observe("a",4);observe("b",28);observe("new",4);
    assert(r.NewcomerDiskPrior("new")>0 && r.NewcomerSurvival("new",at)==1);
    observe("scan",12);
    // A 32-request return interval gives more than half the prior after12
    // intervening requests; a within-burst four-request half-life gives1/8.
    assert(r.NewcomerSurvival("new",at)>.5);
    const auto before=r.NewcomerSurvival("new",at);observe("scan",128);
    assert(r.NewcomerSurvival("new",at)<before);
    assert(r.NewcomerSurvival("missing",at)==0);
    observe("new",4);assert(r.NewcomerDiskPrior("new")==0); // own evidence takes over
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
