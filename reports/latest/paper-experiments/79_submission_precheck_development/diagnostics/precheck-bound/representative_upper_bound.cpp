#include "measured_policy.h"
#include <cassert>
#include <iostream>
#include <random>
using namespace tokenfs_policy;
int main() {
  Options o;
  o.shared_value=o.causal_window=o.burst_reuse=o.adaptive_control=true;
  o.persistent_run_reuse=o.persistent_reuse_immediate_decay=true;
  o.retained_capture=o.bounded_cost_warmup=o.object_weighted_cohort_prior=true;
  o.burst_interval_survival=o.reuse_scaled_exploration=o.novel_reuse_decay=true;
  o.recent_value_floor=o.cohort_reuse_prior=o.shift_reset=true;
  o.affinity_gate=false;
  std::mt19937 rng(79);uint64_t checks=0;
  for(int samples=0;samples<2;++samples) {
    MeasuredPolicy p;
    if(samples) {p.ReadSample(false,4096,21);p.ReadSample(true,4096,10);p.CopySample(4096,8);}
    for(int observation=0;observation<512;++observation) {
      const auto key=std::to_string(rng()%24);
      p.Observe(rng()%3,key,o,rng()%2);
      for(int h=0;h<2;++h)for(int joint=0;joint<2;++joint) {
        o.static_reuse_value=h;o.joint_admission=joint;
        for(uint64_t size:{1024,4096,16384}) {
          const Item incoming{key,size,0};
          const bool representative=p.PotentiallyProfitable(0,incoming,size,size,o);
          for(int gpu=0;gpu<3;++gpu)for(uint64_t quota:{size,size*2,size*16}) {
            // All checks are on a fixed policy snapshot (Plan is pure).
            assert(representative==p.PotentiallyProfitable(gpu,incoming,quota,quota,o));
            assert(representative==p.PotentiallyProfitable(gpu,incoming,quota+size,quota,o));
            ++checks;
          }
          assert(!p.PotentiallyProfitable(1,incoming,size/2,size/2,o));
        }
      }
    }
  }
  std::cout<<"representative upper-bound equality checks="<<checks<<" passed\n";
}
