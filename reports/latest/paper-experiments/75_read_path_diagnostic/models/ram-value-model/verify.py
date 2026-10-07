from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parent
x=json.loads((root/'results.json').read_text());original=json.loads((root.parent/'disk-model/results.json').read_text())
assert len(x['rows'])==10
arms=0;requests=0;summary=[]
for row in x['rows']:
 old=next(r for r in original['rows'] if r['input']==row['input'])
 for policy in ['retained','opportunity74']:
  baseline=row['variants'][policy+'_lru']['arms']
  for a,m in old['variants'][policy]['arms'].items():assert {k:baseline[a][k] for k in m}==m
  for ram in ['lru','disk_value','ram_value']:
   name=policy+'_'+ram;values=row['variants'][name]['arms']
   assert len(values)==4
   for v in values.values():
    assert v['remote']+v['disk_hits']+v['ram_hits']==v['requests']==1152
    arms+=1;requests+=v['requests']
   full=values['Full'];noh=values['NoHotspot'];lru=baseline['Full']
   def costs(v):return 21*v['remote']+10.5*v['disk_hits']+8*v['copies']
   summary.append({'input':row['input'],'variant':name,'ram_delta_vs_noh':full['ram_hits']-noh['ram_hits'],'remote_saved_vs_noh':noh['remote']-full['remote'],'extra_copies_vs_noh':full['copies']-noh['copies'],'algebraic_cost_saving_ms_vs_noh':costs(noh)-costs(full),'algebraic_cost_saving_ms_vs_same_h_lru':costs(lru)-costs(full)})
 for ram in ['lru','disk_value','ram_value']:
  assert row['variants']['retained_'+ram]['arms']['NoHotspot']==row['variants']['opportunity74_'+ram]['arms']['NoHotspot']
 assert row['variants']['retained_disk_value']['arms']['NoHotspot']==row['variants']['retained_ram_value']['arms']['NoHotspot']
assert arms==240
for name in x['rows'][0]['variants']:
 source=(root/name/'replay.cpp').read_text()
 assert 'RAM budget/current-capture invariant' in source
 if not name.endswith('_lru'):
  assert 'if(k!=key)choices.push_back' in source and 'ranked.size()!=2' in source
(root/'summary.json').write_text(json.dumps({'not_measured_time':True,'rows':summary},indent=2)+'\n')
(root/'verification.json').write_text(json.dumps({'passed':True,'model_arms':arms,'total_requests_checked':requests,'lru_exact_baseline_reproduction_arms':80,'same_ram_noh_unchanged_across_h_implementations_pairs':30,'ram_budget_and_incoming_capture_invariant_checked_per_request':True,'pinning_limitation':'Serialized instantaneous-copy model has no pinned old RAM buffers; real pin exclusion/concurrency remains an implementation obligation.'},indent=2)+'\n')
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='manifest.json'}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print((root/'verification.json').read_text())
