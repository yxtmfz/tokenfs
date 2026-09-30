from pathlib import Path
import shutil
root=Path('../hotspot-opportunity-screen');src=Path('src')
shutil.copytree('../hotspot-support-screen/inputs',root/'inputs',dirs_exist_ok=True)
base=Path('../hotspot-support-screen/replay.cpp').read_text()
(root/'replay.cpp').write_text(base)
variants=['retained','deadline','residual','renewal_window']
for variant in variants:
 d=root/variant;d.mkdir(exist_ok=True)
 for name in ['measured_policy.h','run_reuse.h']:shutil.copy2(src/name,d/name)
 if variant=='retained':continue
 p=d/'run_reuse.h';s=p.read_text();method='''  double DiskOpportunity(const std::string& key,uint64_t at,size_t horizon) const {
    const auto it=entries_.find(key);if(it==entries_.end())return 0;
    const auto& e=it->second;if(!e.gap.n)return 0;
    const double gap=std::max(4.0,e.gap.mean);
    const double age=double(at-e.last_start);
    const double confidence=double(e.gap.n)/(e.gap.n+1.0);
    const double spread=std::sqrt(std::max(0.0,e.gap.variance));
    FORMULA
  }
'''
 formulas={
 'deadline':'return double(horizon)/gap*confidence*std::exp2(-std::max(0.0,age-gap)/gap);',
 'residual':'const double until=std::max(gap*0.5,std::abs(gap-age)+spread); return double(horizon)/until*confidence*std::exp2(-std::max(0.0,age-gap)/gap);',
 'renewal_window':'const double until=std::max(0.0,gap-age);return (1+std::max(0.0,double(horizon)-until)/gap)*confidence*std::exp2(-std::max(0.0,age-gap)/gap);'}
 s=s.replace('  size_t Entries() const',method.replace('FORMULA',formulas[variant])+'  size_t Entries() const');p.write_text(s)
 p=d/'measured_policy.h';s=p.read_text();start=s.index('    const double recent=RecentValue',s.index('  double Value('));end=s.index('\n  }',start)
 s=s[:start]+'''    // Disk opportunities count distinct returns, never adjacent RAM repeats.
    const double repeats=run_reuse_.DiskOpportunity(item.key,observations_,o.window);
    const double competition=1.0-(o.adaptive_control?temporal_strength_:1.0)*(1.0-run_reuse_.CompetitionSurvival(item.key));
    return repeats*competition*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;'''+s[end:]
 # No transferred first-run demand in this proposed H variant.
 start=s.index('    if(!o.cohort_reuse_prior',s.index('  double CohortDiskReuse('));end=s.index('\n  }',start)
 s=s[:start]+'    (void)gpu;(void)key;(void)o;return 0;'+s[end:];p.write_text(s)
