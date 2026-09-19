#include "measured_policy.h"
#include <iostream>
using namespace tokenfs_policy;
int main(){MeasuredPolicy p;Options o;o.shift_reset=true;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,500);int resets=0;bool admitted=false;for(int i=0;i<96;i++){const auto key=std::to_string(i%4);resets+=p.Observe(0,key,o,false);admitted|=p.Plan(0,{key,100,0},{},0,400,o).allowed;}std::cout<<"resets="<<resets<<" eventually_admitted="<<admitted<<"\n";return admitted?0:1;}
