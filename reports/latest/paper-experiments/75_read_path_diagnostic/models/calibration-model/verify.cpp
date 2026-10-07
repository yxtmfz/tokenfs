#include "measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main(int argc,char**argv) {
 const std::string gate=argv[1];const uint64_t size=2097152;
 for(const std::string arm:{"Full","NoHotspot","NoAffinity","NoJoint"}) {
  Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;
  o.recent_value_floor=o.cohort_reuse_prior=true;o.static_reuse_value=arm=="NoHotspot";o.joint_admission=arm!="NoJoint";
  MeasuredPolicy p;p.Observe(0,"new",o);
  auto explore=[&](){return p.Plan(0,{"new",size,0}, {},0,4*size,o).explore_headroom;};
  assert(explore());p.CopySample(size,8000);assert(explore()==(gate!="copy_calibrated"));
  p.ReadSample(false,size,21000);assert(explore()==(gate!="copy_calibrated"));
  p.ReadSample(true,size,10500);assert(explore()==(gate=="old"));
  // With free exploration disabled, a first-seen object is not silently copied.
  if(gate!="old") {assert(!p.Plan(0,{"new",size,0},{},0,4*size,o).allowed);assert(!p.PotentiallyProfitable(0,{"new",size,0},0,4*size,o));}
 }
 std::cout<<"passed: all four arms share gate; no-sample calibration, copy-only threshold, full read/copy calibration, first-seen regular admission and optimistic guard\n";
}
