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
  {
    using namespace tokenfs_policy;
    MeasuredPolicy p;Options o;o.adaptive_control=true;o.bounded_cost_warmup=true;
    p.ReadSample(false,100,100,true);p.ReadSample(true,100,20,true);
    p.CopySample(100,100000,true);
    auto free=p.Plan(0,{"cold",100,0},{},0,100,o);
    assert(free.allowed && free.explore_headroom && free.victims.empty());
    assert(!p.Plan(0,{"cold",101,0},{},0,100,o).allowed);
    auto full=p.Plan(0,{"cold",100,0},{{"resident",100,0}},100,100,o);
    assert(!full.allowed && !full.explore_headroom); // no paid displacement as calibration
    for(int i=0;i<19;++i)p.CopySample(100,100,true);
    auto mean=p.Plan(0,{"cold",100,0},{},0,100,o);
    assert(std::abs(mean.copy_us-(100000.0+1900.0)/20)<1e-7);
    p.CopySample(100,100,true);
    assert(std::abs(p.Plan(0,{"cold",100,0},{},0,100,o).copy_us-(mean.copy_us*.95+5))<1e-7);
  }

}
