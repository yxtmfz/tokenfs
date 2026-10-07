#include "disk_demand.h"
#include <cassert>
#include <cmath>
#include <iostream>
using namespace tokenfs_policy;
int main() {
  DiskDemand d;
  d.Observe("a",1,128,false);
  assert(d.Value("a",1,128)==0);
  for(uint64_t t=2;t<102;++t)d.Observe("a",t,128,true);
  assert(d.Value("a",101,128)==0); // RAM-only repeats do not establish disk reuse.
  d.Observe("a",102,128,false);
  assert(d.Value("a",102,128)>0);
  auto value=d.Value("a",102,128);
  d.Observe("a",103,128,true);
  assert(d.Value("a",103,128)<value); // RAM activity advances age, not disk demand.
  assert(d.Value("missing",103,128)==0);
  for(uint64_t t=104;t<300;++t)d.Observe("scan"+std::to_string(t),t,128,false);
  assert(d.Value("a",300,128)==0); // Bounded long history expires.
  d.Observe("end",300,2,false);
  assert(d.Value("end",300,2)==0);
  DiskDemand x,y;
  // History depends on the observed prefix only, not labels or eventual suffix.
  for(uint64_t t=1;t<70;++t) {
    const std::string key=std::to_string((t/4)%3);const bool capture=t%4!=0;
    x.Observe(key,t,128,capture);y.Observe(key,t,128,capture);
    assert(x.Value(key,t,128)==y.Value(key,t,128));
    assert(std::isfinite(x.Value(key,t,128)) && x.Value(key,t,128)>=0);
  }
  std::cout<<"RAM exclusion, prefix causality, age decay and bounded expiry passed\n";
}
