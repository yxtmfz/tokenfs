#include "run_reuse.h"
#include <cassert>
#include <cmath>
int main(){tokenfs_policy::RunReuse r;uint64_t at=0;
 for(int i=0;i<50;++i){r.Observe("A",++at,128);r.Observe("B",++at,128);}
 r.Observe("C",++at,128);assert(std::abs(r.NewcomerDiskPrior("C")-1.0)<1e-12);
 r.Observe("A",++at,128);assert(r.NewcomerDiskPrior("A")==0);
}
