from pathlib import Path
import shutil,subprocess,json,hashlib
root=Path(__file__).resolve().parent
base=root.parent/'hotspot-next-review/ram-value-model'
shutil.copytree(base/'inputs',root/'inputs',dirs_exist_ok=True)
for mode in ['original','run_units']:
 d=root/mode;d.mkdir(exist_ok=True)
 for name in ['measured_policy.h','run_reuse.h','replay.cpp']:shutil.copyfile(base/name,d/name)
 if mode=='run_units':
  p=d/'run_reuse.h';s=p.read_text();old='bool immediate_decay=false) const';assert s.count(old)==1
  s=s.replace(old,'bool immediate_decay=false,bool unit_runs=false) const')
  old='std::max<size_t>(2,horizon)/interval*e.length.mean*confidence*';assert s.count(old)==1
  s=s.replace(old,'std::max<size_t>(2,horizon)/interval*(unit_runs?1.0:e.length.mean)*confidence*')
  p.write_text(s)
  p=d/'measured_policy.h';s=p.read_text();needle='    if(DiskOpportunityEnabled(o)) {\n      const double recent=RecentValue(gpu,item.key,o,incoming)*DiskReuseScale(o);';assert s.count(needle)==1
  branch='''    // Local model counterfactual only: express both H forecasts in observed
    // logical-run units; preserve static NoH, prior, costs, aging and noise.
    if(o.retained_capture && o.persistent_run_reuse && o.causal_window &&
       o.shared_value && o.burst_reuse) {
      const auto* positions=RecentPositions(gpu,item.key,o);
      double runs=positions && !positions->empty()?1.0:0.0;
      if(positions)for(size_t i=1;i<positions->size();++i)
        if((*positions)[i]-(*positions)[i-1]>1)runs+=1.0;
      if(!o.frequency_admission)runs=std::max(0.0,runs-1.0);
      const double recent=runs*Survival(gpu,item.key,o);
      const double persistent=run_reuse_.Estimate(item.key,observations_,o.window,
                                                 o.persistent_reuse_immediate_decay,true);
      double past=std::max(recent,persistent);
      if(o.novel_reuse_decay) {
        const double competition=1.0-(o.adaptive_control?temporal_strength_:1.0)*
            (1.0-run_reuse_.CompetitionSurvival(item.key));
        past=o.recent_value_floor?std::max(recent,persistent*competition):past*competition;
      }
      return std::max(past,CohortDiskReuse(gpu,item.key,o))*
          (o.cost?SavingRate()*item.bytes:1.0)*item.coverage;
    }
'''
  s=s.replace(needle,branch+needle);p.write_text(s)
 subprocess.run(['clang++','-std=c++17','-O2','-Wall','-Wextra',str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
identity={'base':str(base),'source_headers':{n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in ['measured_policy.h','run_reuse.h']},'variants':{mode:{n:hashlib.sha256((root/mode/n).read_bytes()).hexdigest() for n in ['measured_policy.h','run_reuse.h','replay.cpp']} for mode in ['original','run_units']}}
(root/'source-identity.json').write_text(json.dumps(identity,indent=2)+'\n')
