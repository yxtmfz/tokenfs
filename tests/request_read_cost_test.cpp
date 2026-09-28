#include "../src/request_read_cost.h"
#include "../src/measured_policy.h"
#include <cassert>
#include <cmath>
int main(){
  constexpr uint64_t mib=1024*1024;
  RequestReadCost split(mib),whole(mib);
  assert(!split.Add(0,mib-48,10000));
  auto a=split.Add(mib-48,48,500);auto b=whole.Add(0,mib,10500);
  assert(a && b && a->bytes==b->bytes && a->micros==b->micros);
  assert(!split.Finish() && !split.Add(mib,0,1));
  RequestReadCost partial(mib);assert(!partial.Add(0,48,500));
  a=partial.Finish();assert(a && a->bytes==48 && a->micros==500 && !partial.Finish());
  RequestReadCost reordered(mib);
  assert(!reordered.Add(mib/2,mib/2,10000));assert(!reordered.Add(0,mib/2,5000));
  a=reordered.Finish();assert(a && a->bytes==mib && a->micros==15000);
  RequestReadCost empty(mib);assert(!empty.Finish());
  // Exact regression: fragment sizes alone must not reverse faster local I/O.
  tokenfs_policy::MeasuredPolicy p;
  tokenfs_policy::Options o;o.causal_window=true;o.shared_value=true;o.cost=true;
  for(int i=0;i<10;++i)p.Observe(0,"k",o);
  RequestReadCost remote(mib),local(mib);
  assert(!remote.Add(0,mib-944,10000));a=remote.Add(mib-944,944,300);
  assert(!local.Add(0,mib-48,4000));b=local.Add(mib-48,48,100);
  assert(a && b);p.ReadSample(false,a->bytes,a->micros);p.ReadSample(true,b->bytes,b->micros);p.CopySample(mib,5000);
  auto plan=p.Plan(0,{"k",mib,0},{},0,mib,o);
  assert(plan.allowed && std::abs(plan.copy_us-5000)<1e-6);
  tokenfs_policy::MeasuredPolicy broken;
  for(int i=0;i<10;++i)broken.Observe(0,"k",o);
  broken.ReadSample(false,mib-944,10000);broken.ReadSample(false,944,300);
  broken.ReadSample(true,mib-48,4000);broken.ReadSample(true,48,100);broken.CopySample(mib,5000);
  assert(!broken.Plan(0,{"k",mib,0},{},0,mib,o).allowed);
}
