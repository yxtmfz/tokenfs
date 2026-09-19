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
 for(int i=0;i<5;i++)multi.Observe(0,"big",o);
 multi.Observe(0,"x",o);multi.Observe(0,"y",o);
 auto plan=multi.Plan(0,{"big",200,3},{{"x",100,1},{"y",100,2}},200,200,o);
 assert(plan.allowed && plan.victims.size()==2 && plan.displaced_us==160);
 std::cout<<"measured admission invariants passed\n";
}
