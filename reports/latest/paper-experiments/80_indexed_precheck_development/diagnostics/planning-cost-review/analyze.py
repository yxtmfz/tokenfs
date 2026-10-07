from pathlib import Path
import hashlib,json
out=Path(__file__).resolve().parent
repo=out.parents[1]/'tokenfs-eval'
base=repo/'reports/latest/paper-experiments/79_submission_precheck_development/data/development'
inputs={};rows=[]
for case in sorted(base.iterdir()):
 if not case.is_dir():continue
 for arm in ('Full','NoHotspot','NoAffinity','NoJoint','NoSubmitPrecheck'):
  p=case/arm/'result.json';r=json.loads(p.read_text());m=r['metrics'];t=r['completed_with_background_s']
  inputs[str(p.relative_to(repo))]=hashlib.sha256(p.read_bytes()).hexdigest()
  c=case/arm/'config.json';cfg=json.loads(c.read_text())['policy'];inputs[str(c.relative_to(repo))]=hashlib.sha256(c.read_bytes()).hexdigest()
  rows.append(dict(case=case.name,arm=arm,completed_s=t,
    precheck_ms=m.get('submission_precheck_us',0)/1000,
    precheck_fraction_percent=m.get('submission_precheck_us',0)/1e4/t,
    copy_planning_ms=m.get('copy_cost_planning_us',0)/1000,
    copy_planning_fraction_percent=m.get('copy_cost_planning_us',0)/1e4/t,
    selected_domain_plan_calls=m.get('shared_placement_plans',0),
    snapshot_calls=m.get('compact_planning_snapshots',0),
    snapshot_input_rows_sum=m.get('compact_planning_residents',0),
    backend_optimistic_rejects=m.get('shared_optimistic_rejects',0),
    background_submitted=m.get('background_submitted',0),
    efficient_planning=cfg.get('efficient_measured_planning'),
    profile_control_path=cfg.get('profile_control_path')))
source={p:hashlib.sha256((repo/p).read_bytes()).hexdigest() for p in ('src/main.cpp','src/measured_policy.h','src/run_reuse.h','tests/planning_equivalence_test.cpp')}
(out/'evidence.json').write_text(json.dumps(dict(scope='Read-only candidate80 source review and frozen79 data. No candidate or performance run.',source_sha256=source,input_sha256=inputs,rows=rows),indent=2)+'\n')
print('Read',len(inputs),'frozen79 JSON files; wrote',len(rows),'descriptive rows; no production/data modifications')
