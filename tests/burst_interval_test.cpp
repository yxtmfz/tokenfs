#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main() {
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
