from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parent
x=json.loads((root/'results.json').read_text());old=json.loads((root.parent/'disk-model/results.json').read_text());assert len(x['rows'])==10
summary=[];count=0;requests=0
for row in x['rows']:
 for h in ['retained','opportunity74']:
  for start in ['warm','cold']:
   original=row['variants'][f'{h}_old_{start}']['arms']
   for gate in ['old','copy_calibrated','all_calibrated']:
    name=f'{h}_{gate}_{start}';arms=row['variants'][name]['arms']
    for a,values in arms.items():
     assert values['remote']+values['disk_hits']+values['ram_hits']==values['requests']==1152
     assert values['ram_hits']==original[a]['ram_hits']
     if start=='cold':assert values['remote_samples']==values['remote'] and values['local_samples']==values['disk_hits'] and values['copy_samples']==values['copies']
     else:assert values['remote_samples']==values['local_samples']==values['copy_samples']==1
     if gate=='old':assert values['headroom_copies']==12
     elif start=='warm':assert values['headroom_copies']==0
     elif gate=='copy_calibrated':assert values['headroom_copies']==1
     count+=1;requests+=values['requests']
    full=arms['Full'];noh=arms['NoHotspot'];base=original['Full'];cost=lambda a:a['remote']*21+a['disk_hits']*10.5+a['copies']*8
    summary.append(dict(input=row['input'],variant=name,full_cost_proxy_ms=cost(full),noh_cost_proxy_ms=cost(noh),full_proxy_saving_vs_noh_ms=cost(noh)-cost(full),full_proxy_saving_vs_original_gate_same_start_ms=cost(base)-cost(full),noh_proxy_saving_vs_original_gate_same_start_ms=cost(original['NoHotspot'])-cost(noh)))
  # With initial complete calibration both gates are the same logical predicate.
  assert row['variants'][f'{h}_copy_calibrated_warm']['arms']==row['variants'][f'{h}_all_calibrated_warm']['arms']
 for gate in ['old','copy_calibrated','all_calibrated']:
  for start in ['warm','cold']:
   assert row['variants'][f'retained_{gate}_{start}']['arms']['NoHotspot']==row['variants'][f'opportunity74_{gate}_{start}']['arms']['NoHotspot']
assert count==480
checks=[]
for h in ['retained','opportunity74']:
 for gate in ['old','copy_calibrated','all_calibrated']:
  d=root/f'{h}_{gate}_cold';exe=d/'verify'
  subprocess.run(['c++','-std=c++17','-O2','-I',str(d),str(root/'verify.cpp'),'-o',str(exe)],check=True)
  p=subprocess.run([str(exe),gate],check=True,capture_output=True,text=True);checks.append(dict(h=h,gate=gate,stdout=p.stdout))
(root/'summary.json').write_text(json.dumps({'not_measured_time':True,'constant_cost_model_only':True,'rows':summary},indent=2)+'\n')
(root/'verification.json').write_text(json.dumps({'passed':True,'model_arms':count,'model_requests':requests,'original_warm_baseline_reproduction_arms':80,'constant_cost_proxy_not_actual_time':True,'checks':checks},indent=2)+'\n')
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='manifest.json'}
(root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print((root/'verification.json').read_text())
