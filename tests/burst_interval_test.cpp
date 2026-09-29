#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main() {
  {
    Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;
    o.adaptive_control=true;o.reuse_scaled_exploration=true;
    MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,250);
    for(int i=0;i<4;++i)p.Observe(0,"completed",o);
    // An unfinished run cannot justify a larger exploration allowance.
    assert(!p.Plan(0,{"new",100,0},{},0,100,o).allowed);
    p.Observe(0,"new",o);
    const auto headroom=p.Plan(0,{"new",100,0},{},0,100,o);
    assert(headroom.allowed && headroom.explore_headroom && headroom.exploration_reads==4);
    Options reference=o;reference.reuse_scaled_exploration=false;
    assert(!p.Plan(0,{"new",100,0},{},0,100,reference).allowed);
    assert(!p.Plan(0,{"new",100,0},{{"resident",100,0}},100,100,o).allowed);
    assert(!p.Plan(0,{"new",101,0},{},0,100,o).allowed);
    MeasuredPolicy singles;singles.ReadSample(false,100,100);singles.CopySample(100,250);
    for(int i=0;i<20;++i)singles.Observe(0,"scan"+std::to_string(i),o);
    assert(!singles.Plan(0,{"next",100,0},{},0,100,o).allowed);
    MeasuredPolicy costly;costly.ReadSample(false,100,100);costly.CopySample(100,1000);
    for(int i=0;i<4;++i)costly.Observe(0,"a",o);
    costly.Observe(0,"b",o);
    assert(!costly.Plan(0,{"b",100,0},{},0,100,o).allowed);
  }
  Options old;old.causal_window=true;old.shared_value=true;old.burst_reuse=true;
  old.shift_reset=true;old.window=128;old.admission=false;
  Options fixed=old;fixed.burst_interval_survival=true;
  auto loss=[](MeasuredPolicy& p,const Options& o,const std::string& key) {
    return p.Plan(0,{"incoming",100,0},{{key,100,0}},100,100,o).displaced_us;
  };
  MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,20);
  // Recurring runs have a 29-request off-period, not a one-request period.
  for(int cycle=0;cycle<3;++cycle) {
    for(int i=0;i<4;++i)p.Observe(i%3,"stable",fixed);
    for(int i=0;i<28;++i)p.Observe(i%3,"scan"+std::to_string(cycle*28+i),fixed);
  }
  assert(loss(p,fixed,"stable")>5*loss(p,old,"stable"));
  for(int i=0;i<4;++i)p.Observe(0,"one-off",fixed);
  for(int i=0;i<12;++i)p.Observe(0,"other"+std::to_string(i),fixed);
  assert(loss(p,fixed,"one-off")==loss(p,old,"one-off"));
  // Actual staleness still lowers value and the bounded window forgets it.
  const auto before=loss(p,fixed,"stable");
  for(int i=0;i<16;++i)p.Observe(0,"moving"+std::to_string(i),fixed);
  assert(loss(p,fixed,"stable")<before);
  for(int i=0;i<128;++i)p.Observe(0,"new-hot",fixed);
  assert(loss(p,fixed,"stable")==0);
  assert(p.Plan(0,{"new-hot",100,0},{{"stable",100,0}},100,100,fixed).allowed);
  // Non-bursty interleavings and singleton runs keep identical estimates.
  MeasuredPolicy q;
  for(int i=0;i<40;++i)q.Observe(i%3,i%2?"b":"a",fixed);
  assert(loss(q,fixed,"a")==loss(q,old,"a"));
  fixed.burst_reuse=false;
  assert(loss(q,fixed,"a")==loss(q,old,"a"));
  assert(!q.Plan(0,{"oversize",101,0},{},0,100,fixed).allowed);
  assert(!q.Plan(0,{"pinned",100,0},{},100,100,fixed).allowed);
  std::cout<<"burst recurrence, scan decay, shift forgetting and capacity passed\n";
}
