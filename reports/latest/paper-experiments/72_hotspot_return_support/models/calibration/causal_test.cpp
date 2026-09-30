#include "forecast_calibration.h"
#include <cassert>
#include <string>
using namespace tokenfs_policy;
int main(){
 ForecastCalibration c;
 c.Observe("x",1,true);c.Predict("x",1,4,0,1,0);
 assert(c.Pending()==1 && c.Completed(0)==0 && c.Weight(0)==0);
 c.Observe("x",2,false);c.Observe("x",3,false);c.Observe("x",4,false);
 assert(c.Completed(0)==0); // Censored horizons must not vote.
 c.Observe("z",5,false);assert(c.Completed(0)==1 && c.Weight(0)==0);
 c.Predict("y",6,4,0,1,1);c.Observe("y",7,true);
 assert(c.Completed(1)==0);c.Observe("z",10,false);
 assert(c.Completed(1)==1 && c.Weight(1)==1); // Only a disk return is a label.
 for(unsigned i=11;i<100;++i){auto k=std::to_string(i);c.Observe(k,i,true);c.Predict(k,i,4,0,1,0);assert(c.Pending()<=4 && c.Completed(0)<=4);}
}
