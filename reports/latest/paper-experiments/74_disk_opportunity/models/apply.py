from pathlib import Path
p=Path('src/run_reuse.h');s=p.read_text();source=Path('../hotspot-opportunity-screen/deadline/run_reuse.h').read_text();start=source.index('  double DiskOpportunity(');end=source.index('  size_t Entries()',start)
method=source[start:end].replace('    const double spread=std::sqrt(std::max(0.0,e.gap.variance));\n','')
method='''  // Count one possible disk reuse per distinct observed run, not its adjacent
  // RAM-served requests. Do not expire recurrence before its observed mean gap.
  // The forecast uses completed gaps only; overdue reuse still loses value.
'''+method
assert 'DiskOpportunity' not in s;s=s.replace('  size_t Entries() const',method+'  size_t Entries() const');p.write_text(s)
p=Path('src/measured_policy.h');s=p.read_text().replace('  bool recent_value_floor=false;','  bool recent_value_floor=false;\n  bool disk_opportunity_value=false;')
old='''  double PersistentEstimate(const std::string& key,const Options& o) const {
    return'''
new='''  bool DiskOpportunityEnabled(const Options& o) const {
    return o.disk_opportunity_value && !o.static_reuse_value && o.retained_capture &&
      o.persistent_run_reuse && o.causal_window && o.shared_value && o.burst_reuse;
  }
  double PersistentEstimate(const std::string& key,const Options& o) const {
    if(DiskOpportunityEnabled(o))
      return run_reuse_.DiskOpportunity(key,observations_,o.window)/DiskReuseScale(o);
    return'''
assert old in s;s=s.replace(old,new)
s=s.replace('''  double CohortDiskReuse(int gpu,const std::string& key,const Options& o) const {
    if''','''  double CohortDiskReuse(int gpu,const std::string& key,const Options& o) const {
    if(DiskOpportunityEnabled(o))return 0;
    if''')
needle='''    const double recent=RecentValue(gpu,item.key,o,incoming);'''
new='''    if(DiskOpportunityEnabled(o)) {
      const double recent=RecentValue(gpu,item.key,o,incoming)*DiskReuseScale(o);
      const double opportunity=run_reuse_.DiskOpportunity(item.key,observations_,o.window);
      const double competition=1.0-(o.adaptive_control?temporal_strength_:1.0)*(1.0-run_reuse_.CompetitionSurvival(item.key));
      // Recent and long-run forecasts overlap: never add their predictions.
      const double repeats=std::max(recent,opportunity*competition);
      return repeats*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;
    }
'''+needle
assert s.count(needle)==1;s=s.replace(needle,new);p.write_text(s)
p=Path('src/main.cpp');s=p.read_text();needle='  bool recent_value_floor = false;'
if needle not in s:needle='  bool recent_value_floor=false;'
assert needle in s;s=s.replace(needle,needle+'\n  bool disk_opportunity_value=false;')
s=s.replace('config_.cohort_reuse_prior,config_.recent_value_floor};','config_.cohort_reuse_prior,config_.recent_value_floor,config_.disk_opportunity_value};')
needle='  if(root["policy"] && root["policy"]["recent_value_floor"])'
start=s.index(needle);end=s.index('\n',start)
s=s[:end]+'\n  if(root["policy"] && root["policy"]["disk_opportunity_value"]) config.disk_opportunity_value=root["policy"]["disk_opportunity_value"].as<bool>();'+s[end:]
p.write_text(s)
