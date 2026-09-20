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
 std::cout<<"measured admission invariants passed\n";
}
