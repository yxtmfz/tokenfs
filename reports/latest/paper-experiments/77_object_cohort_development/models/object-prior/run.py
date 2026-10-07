from pathlib import Path
import subprocess,json,hashlib,shutil,math
root=Path(__file__).resolve().parent
frozen=Path('/Users/mafuze/Documents/Codex/2026-09-18/new-chat/work/tokenfs-eval/reports/latest/paper-experiments/75_read_path_diagnostic/models/disk-model')
shutil.copytree(frozen/'inputs',root/'inputs',dirs_exist_ok=True)
variants=[(h,p) for h in ['retained','opportunity74'] for p in ['event_prior','object_prior']]
original=json.loads((frozen/'results.json').read_text())
for h,p in variants:
 name=h+'_'+p;d=root/name;d.mkdir(exist_ok=True)
 policy=(frozen/h/'measured_policy.h').read_text();reuse=(frozen/h/'run_reuse.h').read_text();replay=(frozen/h/'replay.cpp').read_text()
 if p=='object_prior':
  old='    return std::min(1.0,double(recent_.size()-entries_.size())/(entries_.size()+1.0));'
  new='''    // Bounded object support, not a calibrated probability: every retained
    // object gets one vote, independent of how many times a hot object returns.
    size_t recurring=0;for(const auto& item:entries_)recurring+=item.second.gap.n>0;
    return double(recurring)/(entries_.size()+1.0);'''
  assert reuse.count(old)==1;reuse=reuse.replace(old,new)
 # Instrument every committed model admission; a positive cohort term need
 # not dominate the max() value, so do not call it a cohort-caused admission.
 replay=replay.replace('#include <map>','#include <map>\n#include <iomanip>')
 replay=replay.replace('i=0,remote=0,copies=0;', 'i=0,remote=0,copies=0,cohort_admissions=0;')
 old='if(selected>=0){for(auto&v:chosen.victims)'
 new='''if(selected>=0){
    cohort_admissions+=chosen.cohort_disk_reuse>0;
    std::cerr<<std::setprecision(17)<<arm<<"\\t"<<i<<"\\t"<<key<<"\\t"<<selected<<"\\t"<<chosen.reason<<"\\t"<<chosen.cohort_disk_reuse<<"\\t"<<chosen.incoming_us<<"\\t"<<chosen.displaced_us<<"\\t"<<chosen.copy_us<<"\\t"<<chosen.uncertainty_us<<"\\t"<<chosen.victims.size()<<"\\n";
    for(auto&v:chosen.victims)'''
 assert old in replay;replay=replay.replace(old,new)
 replay=replay.replace('<<" copies="<<copies;', '<<" copies="<<copies<<" cohort_admissions="<<cohort_admissions;')
 (d/'measured_policy.h').write_text(policy);(d/'run_reuse.h').write_text(reuse);(d/'replay.cpp').write_text(replay)
 subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-I',str(d),str(d/'replay.cpp'),'-o',str(d/'replay')],check=True)
 test='''#include "run_reuse.h"
#include <cassert>
#include <cmath>
int main(){tokenfs_policy::RunReuse r;uint64_t at=0;
 for(int i=0;i<50;++i){r.Observe("A",++at,128);r.Observe("B",++at,128);}
 r.Observe("C",++at,128);assert(std::abs(r.NewcomerDiskPrior("C")-EXPECTED)<1e-12);
 r.Observe("A",++at,128);assert(r.NewcomerDiskPrior("A")==0);
}
'''.replace('EXPECTED','0.5' if p=='object_prior' else '1.0')
 (d/'prior_test.cpp').write_text(test)
 subprocess.run(['c++','-std=c++17','-O2','-I',str(d),str(d/'prior_test.cpp'),'-o',str(d/'prior_test')],check=True)
 subprocess.run([str(d/'prior_test')],check=True)
rows=[];admissions=[];reproduced=0
for f in sorted((root/'inputs').glob('*.txt')):
 row={'input':f.stem,'variants':{}}
 previous=next(r for r in original['rows'] if r['input']==f.stem)
 for h,p in variants:
  name=h+'_'+p;result=subprocess.run([str(root/name/'replay'),str(f),'prior'],capture_output=True,text=True,check=True)
  arms={}
  for line in result.stdout.splitlines():
   cs=line.split();arms[cs[0]]={k:int(v) for k,v in (c.split('=') for c in cs[1:])}
  if p=='event_prior':
   for arm,metrics in previous['variants'][h]['arms'].items():
    assert {k:arms[arm][k] for k in metrics}==metrics,(f,name,arm)
    reproduced+=1
  else:
   prior_noh=row['variants'][h+'_event_prior']['arms']['NoHotspot']
   assert arms['NoHotspot']=={k:prior_noh[k] for k in arms['NoHotspot']},(f,name)
  arm_admissions={a:[] for a in arms}
  for line in result.stderr.splitlines():
   a,t,k,location,reason,cohort,incoming,loss,copy,noise,victims=line.split('\t')
   record={'input':f.stem,'variant':name,'arm':a,'observation':int(t),'key':k,'location':int(location),'reason':reason,'cohort_disk_reuse':float(cohort),'incoming_us':float(incoming),'displaced_us':float(loss),'copy_us':float(copy),'uncertainty_us':float(noise),'victim_count':int(victims)}
   admissions.append(record);arm_admissions[a].append(record)
  for a,m in arms.items():
   assert len(arm_admissions[a])==m['copies']
   assert sum(e['cohort_disk_reuse']>0 for e in arm_admissions[a])==m['cohort_admissions']
   m['cohort_positive_headroom']=sum(e['cohort_disk_reuse']>0 and e['reason']=='capacity_bounded_calibration' for e in arm_admissions[a])
   m['cohort_positive_net_gain']=sum(e['cohort_disk_reuse']>0 and e['reason']=='net_gain' for e in arm_admissions[a])
  row['variants'][name]={'stdout':result.stdout,'arms':arms}
 rows.append(row)
result={'speed_evidence':False,'description':'Fixed 10 known inputs × original/event vs distinct-object newcomer prior × retained/74 H × 4 arms =160 arms. Only NewcomerDiskPrior numerator changed; all other logic, old zero guards, controls, cost constants and geometry unchanged. Instant copies, 21ms remote/10.5ms local/8ms copy; no actual rates/p99. Distinct recurrent entries/(entries+1) is bounded object support, not an unbiased probability; entries have unequal ages and incomplete future-return exposure. Positive cohort value in an admission is association, not proof it drove max()-combined acceptance.','baseline_arms_exactly_reproduced':reproduced,'rows':rows}
(root/'results.json').write_text(json.dumps(result,indent=2)+'\n');(root/'admissions.json').write_text(json.dumps(admissions,indent=2)+'\n')
lines=['# Distinct-object newcomer prior screen','',result['description'],'','Each cell: remote / copies / admissions with positive cohort term.','', '| Input | Variant | Full | NoH | NoP | NoJ | Full positive cohort: headroom / net_gain |','|---|---|---:|---:|---:|---:|---:|']
for row in rows:
 for name,data in row['variants'].items():
  a=data['arms'];cells=[' / '.join(str(a[k][x]) for x in ['remote','copies','cohort_admissions']) for k in ['Full','NoHotspot','NoAffinity','NoJoint']]
  lines.append('| '+row['input']+' | '+name+' | '+' | '.join(cells)+' | '+str(a['Full']['cohort_positive_headroom'])+' / '+str(a['Full']['cohort_positive_net_gain'])+' |')
(root/'tables.md').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))
(root/'verification.json').write_text(json.dumps({'passed':True,'arms':160,'original_reproduced':reproduced,'object_prior_unit_cases':4,'noH_unchanged_all_inputs':True,'admission_counts_reconciled':True},indent=2)+'\n')
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ['replay','prior_test','manifest.json']}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
