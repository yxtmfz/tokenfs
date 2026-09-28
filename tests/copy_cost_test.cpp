#include "../src/copy_cost.h"
#include "../src/measured_policy.h"
#include <cassert>

int main() {
  // A timeline with 8 ms paid planning, 12 ms remaining work and 3 ms paid
  // capture. Moving the already-paid boundary cannot erase future work.
  CopyCostSample a{20000,8000,3000};
  assert(a.Full()==23000 && a.Remaining()==12000);
  CopyCostSample delayed{120000,108000,103000};
  assert(delayed.Remaining()==a.Remaining() && delayed.Full()>a.Full());
  bool bad=false;try{CopyCostSample{1,2,0}.Remaining();}catch(const std::logic_error&){bad=true;}assert(bad);
  for(bool incremental:{false,true}) {
    tokenfs_policy::MeasuredPolicy p;tokenfs_policy::Options o;
    o.causal_window=true;o.shared_value=true;
    p.Observe(0,"k",o);p.Observe(0,"k",o);p.Observe(0,"k",o);
    p.ReadSample(false,1000,15000);p.ReadSample(true,1000,5000);
    p.CopySample(1000,a.Charge(incremental));
    const auto plan=p.Plan(0,{"k",1000,0},{},0,1000,o);
    assert(plan.allowed==incremental && plan.copy_us==a.Charge(incremental));
    // No cached plan may override newly pinned capacity at execution time.
    const auto pinned=p.Plan(0,{"k",1000,0},{},1000,1000,o);
    assert(!pinned.allowed && pinned.reason=="pinned_capacity");
    // A later request updates demand normally; the fix freezes no forecasts.
    p.Observe(1,"other",o);
    const auto next=p.Plan(0,{"k",1000,0},{},0,1000,o);
    assert(next.copy_us==a.Charge(incremental));
  }
}
