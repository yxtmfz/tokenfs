from pathlib import Path
import json,hashlib,sys,datetime,tarfile,subprocess
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';sys.path.insert(0,str(r/'scripts'))
from paper_minimal_study import SOURCES
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
pre={host:json.loads((w/f'paper-minimal-preflight-{host}.json').read_text()) for host in ['cn7','cn8']}
hashes={p:sha(r/p) for p in SOURCES}
for v in pre.values():assert v['source_hashes']==hashes and v['spec_sha256']==sha(r/'study-configs/paper-minimal-confirmation-01.json') and not v['remaining_mounts']
assert pre['cn7']['binary_sha256']==pre['cn8']['binary_sha256']
freeze=dict(algorithm_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip(),frozen_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_hashes=hashes,binary_sha256=pre['cn7']['binary_sha256'],spec_sha256=sha(r/'study-configs/paper-minimal-confirmation-01.json'),sensitivity_spec_sha256=sha(r/'study-configs/paper-minimal-sensitivity-01.json'),plan_sha256=sha(r/'docs/paper-minimal-plan.md'),public_window_manifest_sha256=sha(r/'study-configs/paper-minimal-public-windows.json'),planned_confirmation_runs=336,planned_sensitivity_runs=12,per_family_alpha=0.05,primary_tests=16,mechanism_tests=3,remote_diagnostic_tests=4,paired_blocks_per_scene=12,preflight=pre,additional_correctness_references=[],rule='Freeze after 28 development runs and 28 correctness cases per host; unchanged H/J algorithm, no later policy tuning or significance-based sample extension; storage-only, affinity disabled')
p=r/'study-configs/paper-minimal-freeze-01.json';assert not p.exists();p.write_text(json.dumps(freeze,indent=2)+'\n')
with tarfile.open(w/'paper-minimal-freeze-launch.tar.gz','w:gz') as t:t.add(p,arcname=str(p.relative_to(r)))
print(json.dumps(dict(binary_sha256=freeze['binary_sha256'],freeze_sha256=sha(p))))
