from pathlib import Path
import shutil,subprocess,json
root=Path('../hotspot-opportunity-screen');variants=['recent_floor','competition_all','residual_floor','observed_repeat']
for v in variants:
 d=root/v;d.mkdir(exist_ok=True)
 shutil.copy2(root/'deadline/run_reuse.h',d/'run_reuse.h')
 s=Path('src/measured_policy.h').read_text()
 start=s.index('    if(!o.cohort_reuse_prior',s.index('  double CohortDiskReuse('));end=s.index('\n  }',start)
 s=s[:start]+'    (void)gpu;(void)key;(void)o;return 0;'+s[end:]
 start=s.index('    const double recent=RecentValue',s.index('  double Value('));end=s.index('\n  }',start)
 formula={
 'recent_floor':'const double repeats=std::max(recent, opportunity*competition);',
 'competition_all':'const double repeats=std::max(recent, opportunity)*competition;',
 'residual_floor':'const double repeats=std::max(recent, opportunity*competition);',
 'observed_repeat':'const double repeats=recent*competition;'}[v]
 s=s[:start]+'''    const double recent=RecentValue(gpu,item.key,o,incoming)*DiskReuseScale(o);
    const double opportunity=run_reuse_.DiskOpportunity(item.key,observations_,o.window);
    const double competition=1.0-(o.adaptive_control?temporal_strength_:1.0)*(1.0-run_reuse_.CompetitionSurvival(item.key));
    '''+formula+'''
    return repeats*(o.cost?SavingRate()*item.bytes:1.0)*item.coverage;'''+s[end:]
 (d/'measured_policy.h').write_text(s)
 if v=='residual_floor':shutil.copy2(root/'residual/run_reuse.h',d/'run_reuse.h')
 subprocess.run(['c++','-std=c++17','-O2','-I',str(d),str(root/'replay.cpp'),'-o',str(d/'replay')],check=True)
out=[]
for p in sorted((root/'inputs').glob('*.txt')):
 row=dict(input=p.stem,variants={})
 for v in variants:
  x=subprocess.run([str(root/v/'replay'),str(p),'prior'],check=True,capture_output=True,text=True)
  row['variants'][v]=x.stdout.splitlines()
 out.append(row)
 print(p.stem, *[v+': '+r[0] for v,r in row['variants'].items()],sep='\n')
(root/'combined-screen.json').write_text(json.dumps(dict(speed_evidence=False,rows=out),indent=2)+'\n')
