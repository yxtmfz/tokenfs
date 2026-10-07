#include <algorithm>
#include <cmath>
#include <cstdint>
#include <deque>
#include <mutex>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>
#include <map>
#include <stdexcept>
#include <cassert>
#include <iostream>
#include "run_reuse.h"
#define private public
#include "measured_policy.h"
#undef private
using namespace tokenfs_policy;
Options opts(){Options o;o.causal_window=o.shared_value=o.burst_reuse=o.adaptive_control=o.efficient_planning=o.burst_interval_survival=o.reuse_scaled_exploration=o.persistent_run_reuse=o.persistent_reuse_immediate_decay=o.novel_reuse_decay=o.retained_capture=o.bounded_cost_warmup=o.shift_reset=true;o.recent_value_floor=o.cohort_reuse_prior=true;return o;}
int main(int argc,char**argv) {
 const bool hits=std::string(argv[1])=="hits";auto o=opts();MeasuredPolicy p;
 assert(p.OutcomeDiscount()==.5);
 p.Observe(0,"a",o);p.Observe(0,"a",o,true);
 assert(!p.run_reuse_.HasCompletedReturn("a"));p.CopyInstalled(0,"a",o);
 assert(p.copy_outcomes_.at({0,"a"}).newcomer);
 // Logical/RAM observations never count as realized storage hits.
 for(int i=0;i<10;++i)p.Observe(0,"a",o,true);
 assert(p.copy_outcomes_.at({0,"a"}).hits==0);
 p.CopyDiskHit(0,"a",o);p.CopyDiskHit(0,"a",o);p.CopyEvicted(0,"a",o);
 assert(p.outcome_closed_newcomers_==1 && p.closed_success_sum_==1 && p.closed_hit_sum_==2);
 assert(std::abs(p.OutcomeDiscount()-(hits?1.0:2.0/3))<1e-12);
 p.Observe(0,"b",o);p.CopyInstalled(1,"b",o);p.CopyEvicted(1,"b",o);
 assert(p.closed_newcomer_outcomes_.size()==2 && p.closed_success_sum_==1 && p.closed_hit_sum_==2);
 assert(std::abs(p.OutcomeDiscount()-(hits?.75:.5))<1e-12);
 p.Observe(0,"c",o);p.CopyInstalled(0,"c",o);
 const double before=p.OutcomeDiscount();for(int i=0;i<100;++i)p.CopyDiskHit(0,"c",o);
 assert(p.OutcomeDiscount()==before && p.closed_newcomer_outcomes_.size()==2);
 // Recurrent objects cannot train the unseen newcomer prior.
 p.Observe(0,"d",o);p.Observe(0,"x",o);p.Observe(0,"d",o);
 assert(p.run_reuse_.HasCompletedReturn("d"));p.CopyInstalled(0,"d",o);
 assert(!p.copy_outcomes_.at({0,"d"}).newcomer);p.CopyDiskHit(0,"d",o);p.CopyEvicted(0,"d",o);
 assert(p.OutcomeDiscount()==before && p.outcome_closed_newcomers_==2 && p.outcome_closed_all_==3);
 // A completed resident is removed from active state exactly once.
 bool failed=false;try{p.CopyEvicted(0,"d",o);}catch(const std::runtime_error&){failed=true;}assert(failed);
 o.window=2;
 for(int i=0;i<10;++i){auto key="fresh"+std::to_string(i);p.Observe(0,key,o);p.CopyInstalled(2,key,o);p.CopyEvicted(2,key,o);}
 assert(p.closed_newcomer_outcomes_.size()==2 && p.closed_success_sum_==0 && p.closed_hit_sum_==0);
 assert(p.OutcomeDiscount()==.25);
 assert(p.copy_outcomes_.size()==1 && p.copy_outcomes_.at({0,"c"}).hits==100);
 // H disabled means no feedback state or effect.
 o.static_reuse_value=true;MeasuredPolicy q;q.Observe(0,"a",o);q.CopyInstalled(0,"a",o);q.CopyDiskHit(0,"a",o);q.CopyEvicted(0,"a",o);
 assert(q.copy_outcomes_.empty() && q.closed_newcomer_outcomes_.empty() && q.outcome_installed_==0);
 std::cout<<"passed: newcomer distinct-run classification, RAM excludes outcomes, completed residence only, censored live copies, hit/success formulas, recurrent exclusion, bounded history, exact lifecycle, NoH isolation\n";
}
