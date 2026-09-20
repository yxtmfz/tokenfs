#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main(){
 Options o;o.window=8;MeasuredPolicy p;
 p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,160);
 p.Observe(0,"a",o);
 assert(!p.Plan(0,{"a",100,1},{},0,100,o).allowed);
 p.Observe(0,"a",o); // One expected future hit cannot repay the verified copy.
 assert(p.Plan(0,{"a",100,1},{},0,100,o).reason=="copy_cost");
 p.Observe(0,"a",o);p.Observe(0,"a",o);
 assert(p.Plan(0,{"a",100,1},{},0,100,o).allowed);
 assert(!p.Plan(1,{"a",100,1},{},0,100,o).allowed); // No leakage across GPU domains.
 auto hot=p.Plan(0,{"a",100,1},{{"b",100,0}},100,100,o);assert(hot.allowed && hot.victims.size()==1);
 assert(!p.Plan(0,{"a",101,1},{},0,100,o).allowed);
 for(int i=0;i<8;i++)p.Observe(0,"b",o);
 assert(p.Frequency(0,"a")==0 && p.Entries()==1);
 assert(!p.Plan(0,{"a",100,1},{{"b",100,0}},100,100,o).allowed);
 Options no=o;no.admission=false;
 assert(p.Plan(0,{"a",100,1},{{"b",100,0}},100,100,no).allowed);
 assert(!p.Plan(0,{"a",100,1},{},100,100,no).allowed); // Cannot evict pinned residents.
 MeasuredPolicy q;Options cumulative=o;cumulative.aging=false;
 for(int i=0;i<20;i++)q.Observe(0,"a",cumulative);
 for(int i=0;i<20;i++)q.Observe(0,"b",cumulative);
 assert(q.Frequency(0,"a")==20);
 // Multiple victims are charged together, not just the first one.
 MeasuredPolicy multi;multi.ReadSample(false,100,100);multi.ReadSample(true,100,20);multi.CopySample(100,160);
 Options wide=o;wide.window=16;
 for(int i=0;i<6;i++)multi.Observe(0,"big",wide);
 for(int i=0;i<2;i++){multi.Observe(0,"x",wide);multi.Observe(0,"y",wide);}
 auto plan=multi.Plan(0,{"big",200,3},{{"x",100,1},{"y",100,2}},200,200,wide);
 assert(plan.allowed && plan.victims.size()==2 && plan.displaced_us==160);
 // Initial over-capacity state must free the excess as well as incoming bytes.
 assert(!p.Plan(0,{"a",100,1},{{"b",100,0}},150,100,no).allowed);
 // Removing the cost model must not silently count the current miss as a future hit.
 MeasuredPolicy isolate;Options unit=o;unit.cost=false;
 isolate.Observe(0,"x",unit);isolate.Observe(0,"x",unit);isolate.Observe(0,"v",unit);
 const auto repeat_estimate=isolate.Plan(0,{"x",100,2},{{"v",100,1}},100,100,unit);
 assert(repeat_estimate.incoming_us==1 && repeat_estimate.displaced_us==0);
 unit.frequency_admission=true; // Explicit frequency-comparator baseline instead.
 const auto raw_frequency=isolate.Plan(0,{"x",100,2},{{"v",100,1}},100,100,unit);
 assert(raw_frequency.incoming_us==2 && raw_frequency.displaced_us==1);
 MeasuredPolicy changing;Options adapt=o;adapt.window=128;adapt.shift_reset=true;
 for(int i=0;i<64;i++)changing.Observe(0,"old",adapt,true);
 bool detected=false;
 for(int i=0;i<8;i++)detected=changing.Observe(0,i%2?"new-a":"new-b",adapt,false)||detected;
 assert(detected && changing.Frequency(0,"old")==0);
 MeasuredPolicy scan;
 for(int i=0;i<64;i++)scan.Observe(0,"old",adapt,true);
 for(int i=0;i<8;i++)assert(!scan.Observe(0,std::to_string(i),adapt,false));
 assert(scan.Frequency(0,"old")==64); // One-off scans must not force a reset.
 // Cold repeated misses are not a demand change. Even expensive copies must
 // eventually become admissible when enough repeat evidence accumulates.
 MeasuredPolicy warming;warming.ReadSample(false,100,100);warming.ReadSample(true,100,20);warming.CopySample(100,500);
 bool eventually_admitted=false;
 for(int i=0;i<96;i++) {
   const auto key=std::to_string(i%4);
   assert(!warming.Observe(0,key,adapt,false));
   eventually_admitted=eventually_admitted || warming.Plan(0,{key,100,0},{},0,400,adapt).allowed;
 }
  assert(eventually_admitted);
  // Joint admission must charge the loss of the selected victims. The independent
  // comparator keeps the same victim ordering and physical capacity protection.
  MeasuredPolicy coupled;Options joint;o=Options{};joint.cost=false;
  for(int i=0;i<10;i++)coupled.Observe(0,"resident",joint);
  for(int i=0;i<3;i++)coupled.Observe(0,"incoming",joint);
  auto reject=coupled.Plan(0,{"incoming",100,2},{{"resident",100,1}},100,100,joint);
  assert(!reject.allowed && reject.reason=="victim_loss");
  joint.joint_admission=false;
  auto accept=coupled.Plan(0,{"incoming",100,2},{{"resident",100,1}},100,100,joint);
  assert(accept.allowed && accept.displaced_us==reject.displaced_us);
  assert(!coupled.Plan(0,{"incoming",101,2},{},0,100,joint).allowed);
  // Affinity is derived from past global observations; balanced sharing remains
  // admissible, and an old dominant caller disappears after the fixed window.
  MeasuredPolicy placed;Options affinity;affinity.cost=false;affinity.track_affinity=true;
  affinity.affinity_gate=true;affinity.affinity_window=32;
  for(int i=0;i<12;i++)placed.Observe(0,"shared",affinity);
  for(int i=0;i<3;i++)placed.Observe(1,"shared",affinity);
  assert(placed.Plan(1,{"shared",100,0},{},0,100,affinity).reason=="affinity");
  Options ungated=affinity;ungated.affinity_gate=false;
  assert(placed.Plan(1,{"shared",100,0},{},0,100,ungated).allowed);
  for(int i=0;i<3;i++)placed.Observe(1,"shared",affinity);
  assert(placed.Plan(1,{"shared",100,0},{},0,100,affinity).allowed);
  for(int i=0;i<32;i++)placed.Observe(1,"shared",affinity);
  assert(placed.Plan(0,{"shared",100,0},{},0,100,affinity).reason=="affinity");
  // A profitable minority caller must not wait to outvote an old dominant one.
  MeasuredPolicy minority;Options recent=affinity;recent.affinity_recent_demand=true;
  for(int i=0;i<20;i++)minority.Observe(0,"shared",recent);
  for(int i=0;i<4;i++)minority.Observe(1,"shared",recent);
  Options legacy=recent;legacy.affinity_recent_demand=false;
  assert(minority.Plan(1,{"shared",100,0},{},0,100,legacy).reason=="affinity");
  assert(minority.Plan(1,{"shared",100,0},{},0,100,recent).allowed);
  // Traffic in other domains ages the affinity of an idle domain. Re-entry may
  // replace stale residents without resetting hotspot history or using the future.
  MeasuredPolicy reentry;
  for(int i=0;i<20;i++)reentry.Observe(0,"stale",recent);
  for(int i=0;i<32;i++)reentry.Observe(1,"elsewhere",recent);
  for(int i=0;i<3;i++)reentry.Observe(0,"new",recent);
  Options off=recent;off.affinity_gate=false;
  assert(reentry.Plan(0,{"new",100,1},{{"stale",100,0}},100,100,off).reason=="victim_loss");
  auto fresh=reentry.Plan(0,{"new",100,1},{{"stale",100,0}},100,100,recent);
  assert(fresh.allowed && fresh.displaced_us==0 && fresh.affinity_adjusted_items==1);
  // With one caller and equal windows, the new affinity model is identical to
  // the domain-only estimate; it must not be a hidden single-domain reset.
  MeasuredPolicy single;recent.window=recent.affinity_window=8;off=recent;off.affinity_gate=false;
  for(int i=0;i<40;i++) {
    auto key=std::to_string(i%3);single.Observe(0,key,recent);
    auto on_plan=single.Plan(0,{key,100,1},{{"0",100,0}},100,200,recent);
    auto off_plan=single.Plan(0,{key,100,1},{{"0",100,0}},100,200,off);
    assert(on_plan.allowed==off_plan.allowed && on_plan.incoming_us==off_plan.incoming_us);
    assert(on_plan.affinity_adjusted_items==0);
  }
  // Old per-domain reuse alone cannot admit a new one-off visit after long idle.
  reentry.Observe(0,"stale",recent);
  assert(!reentry.Plan(0,{"stale",100,0},{},0,100,recent).allowed);
 std::cout<<"measured admission invariants passed\n";
}
