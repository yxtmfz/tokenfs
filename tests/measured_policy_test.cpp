#include "../src/measured_policy.h"
#include <cassert>
#include <iostream>
using namespace tokenfs_policy;
int main(){
 {
  Options o;o.causal_window=true;o.shared_value=true;o.burst_reuse=true;
  MeasuredPolicy p;p.ReadSample(false,100,100);p.ReadSample(true,100,20);p.CopySample(100,40);
  // Learn unequal observed runs; no fixed test burst length in the policy.
  for(int k=0;k<12;++k)for(int j=0;j<(k%2?3:5);++j)p.Observe(j%3,"old"+std::to_string(k),o);
  p.Observe(2,"new",o);
  auto forecast=p.Plan(2,{"new",100,0},{},0,100,o);
  assert(forecast.allowed && forecast.affinity_incoming_count==1 && forecast.burst_remaining>2);
  Options off=o;off.burst_reuse=false;
  assert(!p.Plan(2,{"new",100,0},{},0,100,off).allowed);
  assert(p.HasReuseEvidence(2,"new",o) && !p.HasReuseEvidence(2,"new",off));
  auto symmetric=p.Plan(2,{"new",100,0},{{"new",100,1}},100,100,o);
  assert(symmetric.incoming_us==symmetric.displaced_us && !symmetric.allowed);
  assert(!p.Plan(2,{"new",101,0},{},0,100,o).allowed);
  assert(!p.Plan(2,{"new",100,0},{},100,100,o).allowed); // pinned capacity
  p.CopySample(100,100000);
  assert(!p.Plan(2,{"new",100,0},{},0,100,o).allowed);
  p.Observe(0,"other",o);
  assert(p.Plan(2,{"new",100,0},{},0,100,o).burst_remaining==0);
  for(int k=0;k<160;++k)p.Observe(0,"scan"+std::to_string(k),o);
  assert(!p.HasReuseEvidence(0,"scan159",o)); // short-term adaptation to no reuse
  MeasuredPolicy cold;
  cold.Observe(0,"first",o);assert(!cold.HasReuseEvidence(0,"first",o));
  for(int j=0;j<100;++j)cold.Observe(0,"first",o);
  cold.Observe(0,"next",o);assert(!cold.HasReuseEvidence(0,"next",o)); // no forecast from one run
 }

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
  // After a concentrated caller handover, borrow only established reuse of a
  // globally hot object. The existing copy-cost and victim-loss tests still apply.
  MeasuredPolicy transfer;recent.affinity_window=128;
  for(int i=0;i<24;i++)transfer.Observe(0,"shared",recent);
  transfer.Observe(1,"a",recent);transfer.Observe(1,"b",recent);
  transfer.Observe(1,"shared",recent);
  Options off=recent;off.affinity_gate=false;
  assert(transfer.Plan(1,{"shared",100,1},{},0,100,off).reason=="no_reuse");
  auto borrowed=transfer.Plan(1,{"shared",100,1},{},0,100,recent);
  assert(borrowed.allowed && borrowed.affinity_adjusted_items==1 && borrowed.affinity_incoming_count>1);
  // A cold object and an unrelated resident are not inflated by caller handover.
  transfer.Observe(1,"cold",recent);
  assert(!transfer.Plan(1,{"cold",100,1},{},0,100,recent).allowed);
  auto resident_on=transfer.Plan(1,{"shared",100,1},{{"a",100,0}},100,100,recent);
  auto resident_off=transfer.Plan(1,{"shared",100,1},{{"a",100,0}},100,100,off);
  assert(resident_on.displaced_us==resident_off.displaced_us);
  // A just-copied object must retain the same predicted reuse as an arrival.
  // Arrival-only boosting would make this equal-value replacement look profitable.
  auto symmetric=transfer.Plan(1,{"shared",100,1},{{"shared",100,0}},100,100,recent);
  assert(symmetric.incoming_us==symmetric.displaced_us && !symmetric.allowed);
  transfer.ReadSample(false,100,100);transfer.ReadSample(true,100,20);transfer.CopySample(100,100000);
  Options costly=recent;costly.cost=true;
  assert(transfer.Plan(1,{"shared",100,1},{},0,100,costly).reason=="copy_cost");
  // The forecast decays instead of disappearing when the short-window detector
  // turns off. Both arrival and resident retain equal value throughout decay.
  const auto before_decay=transfer.AdmissionFrequency(1,"shared",recent);
  for(int i=0;i<8;i++)transfer.Observe(2,"other",recent);
  const auto after_decay=transfer.AdmissionFrequency(1,"shared",recent);
  assert(after_decay>1 && after_decay<before_decay);
  auto decayed=transfer.Plan(1,{"shared",100,1},{{"shared",100,0}},100,100,recent);
  assert(decayed.incoming_us==decayed.displaced_us);
  // Execution rechecks cannot use expired global evidence.
  for(int i=0;i<128;i++)transfer.Observe(2,"other",recent);
  assert(transfer.AdmissionFrequency(1,"shared",recent)==1);
  assert(transfer.Plan(1,{"shared",100,1},{},0,100,recent).reason=="no_reuse");
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
 // Returning destinations may discard stale local popularity only with an
 // observed hot-object handover; ordinary inactivity alone is insufficient.
 MeasuredPolicy epochs;Options epoch=recent;epoch.affinity_window=epoch.window=128;
 epoch.affinity_handover_epoch=true;epoch.shift_reset=false;epoch.cost=false;
 for(int i=0;i<24;i++)epochs.Observe(1,"old-task",epoch);
 for(int i=0;i<64;i++)epochs.Observe(0,"new-task",epoch);
 bool context_reset=false;
 epochs.Observe(1,"x",epoch,false,&context_reset);assert(!context_reset);
 epochs.Observe(1,"y",epoch,false,&context_reset);assert(!context_reset);
 epochs.Observe(1,"new-task",epoch,false,&context_reset);assert(context_reset);
 assert(epochs.Frequency(1,"old-task")==0 && epochs.Frequency(1,"x")==1);
 auto epoch_admit=epochs.Plan(1,{"new-task",100,1},{{"old-task",100,0}},100,100,epoch);
 assert(epoch_admit.allowed && epoch_admit.displaced_us==0);
 MeasuredPolicy epoch_off;Options disabled_epoch=epoch;disabled_epoch.affinity_gate=false;
 for(int i=0;i<24;i++)epoch_off.Observe(1,"old-task",disabled_epoch);
 for(int i=0;i<64;i++)epoch_off.Observe(0,"new-task",disabled_epoch);
 epoch_off.Observe(1,"x",disabled_epoch);epoch_off.Observe(1,"y",disabled_epoch);
 epoch_off.Observe(1,"new-task",disabled_epoch,false,&context_reset);assert(!context_reset);
 assert(epoch_off.Frequency(1,"old-task")==24);
 MeasuredPolicy no_transfer;
 for(int i=0;i<24;i++)no_transfer.Observe(1,"old-task",epoch);
 for(int i=0;i<64;i++)no_transfer.Observe(0,"unrelated",epoch);
 for(int i=0;i<4;i++){no_transfer.Observe(1,"cold-new",epoch,false,&context_reset);assert(!context_reset);}
 assert(no_transfer.Frequency(1,"old-task")==24);
 // A shared copy serves all consumers, independent of its resident location.
 Options shared;shared.shared_value=true;shared.cost=false;
 MeasuredPolicy reuse;
 for(int i=0;i<4;++i)reuse.Observe(i%2,"shared",shared,true);
 assert(reuse.AdmissionFrequency(2,"shared",shared)==4);
 assert(reuse.Frequency(2,"shared")==0);
 for(int i=0;i<6;++i)reuse.Observe(1,"valuable",shared,true);
 assert(!reuse.Plan(2,{"shared",100,0},{{"valuable",100,0}},100,100,shared).allowed);
 // Evicting a duplicate with another readable copy does not destroy coverage.
 auto duplicate=reuse.Plan(2,{"shared",100,0},{{"valuable",100,0,0.0}},100,100,shared);
 assert(duplicate.allowed && duplicate.displaced_us==0);
 auto independent=shared;independent.joint_admission=false;
 assert(reuse.Plan(2,{"shared",100,0},{{"valuable",100,0}},100,100,independent).allowed);
 MeasuredPolicy shared_coupled;shared.shift_reset=true;
 for(int i=0;i<64;++i)shared_coupled.Observe(0,"stale",shared,true);
 for(int i=0;i<3;++i)shared_coupled.Observe(1,"stale",shared,true);
 for(int i=0;i<8;++i)shared_coupled.Observe(0,i%2?"next-a":"next-b",shared,false);
 assert(shared_coupled.AdmissionFrequency(2,"stale",shared)==3); // Keep other consumers' evidence.
 // A global observation clock expires inactive consumers' evidence too.
 Options causal;causal.causal_window=true;causal.shared_value=true;
 causal.cost=false;causal.window=16;
 MeasuredPolicy aligned;
 for(int i=0;i<8;++i)aligned.Observe(i%2,"shared",causal,true);
 assert(aligned.AdmissionFrequency(2,"shared",causal)==8);
 for(int i=0;i<16;++i)aligned.Observe(2,"other",causal,true);
 assert(aligned.Frequency(0,"shared")==4);
 assert(aligned.AdmissionFrequency(2,"shared",causal)==0);
 // H ages overdue reuse, not the incoming side alone; no cache-state trigger.
 MeasuredPolicy residual;causal.window=128;
 for(int i=0;i<16;++i)residual.Observe(0,"old",causal,true);
 for(int i=0;i<8;++i)residual.Observe(0,"new",causal,false);
 const auto stale=residual.Plan(0,{"new",100,0},{{"old",100,0}},100,100,causal);
 assert(!stale.allowed && stale.displaced_us==15);
 causal.shift_reset=true;
 const auto adapted=residual.Plan(0,{"new",100,0},{{"old",100,0}},100,100,causal);
 assert(adapted.allowed && adapted.displaced_us==3.75 && adapted.survival_adjusted_items==1);
 const auto same=residual.Plan(0,{"old",100,0},{{"old",100,0}},100,100,causal);
 assert(same.incoming_us==same.displaced_us && !same.allowed);
 // P uses all recent consumers, not unrelated objects or destination identity.
 causal.shared_value=false;
 assert(residual.AdmissionFrequency(1,"new",causal)==0);
 causal.shared_value=true;
 assert(residual.AdmissionFrequency(1,"new",causal)==8);
 const auto absent=residual.Plan(0,{"absent",100,0},{},0,100,causal);
 assert(!absent.allowed && absent.reason=="no_reuse");
 std::cout<<"measured admission invariants passed\n";
}
