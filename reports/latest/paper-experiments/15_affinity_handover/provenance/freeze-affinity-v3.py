from pathlib import Path
import json,hashlib,sys,datetime,tarfile,subprocess
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';sys.path.insert(0,str(r/'scripts'))
from affinity_v3_study import SOURCES
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
pre={host:json.loads((w/f'affinity-v3-preflight-{host}.json').read_text()) for host in ['cn7','cn8']}
hashes={p:sha(r/p) for p in SOURCES}
for v in pre.values():assert v['source_hashes']==hashes and v['spec_sha256']==sha(r/'study-configs/affinity-v3-confirmation-01.json') and not v['remaining_mounts']
assert pre['cn7']['binary_sha256']==pre['cn8']['binary_sha256']
freeze=dict(algorithm_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_hashes=hashes,binary_sha256=pre['cn7']['binary_sha256'],spec_sha256=sha(r/'study-configs/affinity-v3-confirmation-01.json'),public_window_manifest_sha256=sha(r/'study-configs/affinity-v3-public-windows.json'),planned_confirmation_runs=288,per_study_family_alpha=0.025,maximum_confirmation_studies_in_this_task=2,previous_failed_confirmation='reports/latest/paper-experiments/14_affinity_refinement',previous_confirmation_comparisons_sha256=sha(r/'reports/latest/paper-experiments/14_affinity_refinement/confirmation/comparisons.json'),paired_blocks_per_scene=12,preflight=pre,additional_correctness_references=[],rule='Freeze after 48 development runs and 24 correctness cases per host; no later policy tuning or significance-based sample extension')
p=r/'study-configs/affinity-v3-freeze-01.json';assert not p.exists();p.write_text(json.dumps(freeze,indent=2)+'\n')
with tarfile.open(w/'affinity-v3-freeze-launch.tar.gz','w:gz') as t:t.add(p,arcname=str(p.relative_to(r)))
print(json.dumps(dict(binary_sha256=freeze['binary_sha256'],freeze_sha256=sha(p))))
