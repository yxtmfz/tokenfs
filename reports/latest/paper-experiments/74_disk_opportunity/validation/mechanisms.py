import json,math,sys
from pathlib import Path
root=Path(sys.argv[1]);out=Path(sys.argv[2]);rows=[]
parts=['# 第74轮机制计数\n','所有字段按两轮求和；复制使用PROMOTE_READY/REPLICATE_READY事件计数，不能用仅测量策略记录的copy_cost_samples给SIEVE计数。\n','|场景|策略|远端MiB|完成复制|CPU s|规划快照|乐观拒绝|','|---|---|---:|---:|---:|---:|---:|']
for scene in ['moving_shared','public_toolagent']:
 for arm in ['Full','NoHotspot','NoAffinity','NoJoint','PoolSIEVE1','OldFull']:
  paths=sorted(root.glob(scene+'-*/'+arm+'/result.json'));assert len(paths)==2
  rs=[json.loads(p.read_text()) for p in paths]
  copies=[sum(e['action'] in ['PROMOTE_READY','REPLICATE_READY','REPLICA_READY'] for e in json.loads((p.parent/'policy-events.json').read_text())) for p in paths]
  row=dict(scene=scene,arm=arm,remote_mib=sum(r['metrics'].get('read_remote_bytes',0) for r in rs)/1048576,copies=sum(copies),copies_by_round=copies,cpu_s=math.fsum(r['daemon_cpu_s'] for r in rs),snapshots=sum(r['metrics'].get('compact_planning_snapshots',0) for r in rs),optimistic_rejects=sum(r['metrics'].get('shared_optimistic_rejects',0) for r in rs))
  rows.append(row);parts.append(f"|{scene}|{arm}|{row['remote_mib']:.0f}|{row['copies']}|{row['cpu_s']:.2f}|{row['snapshots']}|{row['optimistic_rejects']}|")
(out/'mechanisms.json').write_text(json.dumps(rows,indent=2)+'\n');(out/'mechanisms.md').write_text('\n'.join(parts)+'\n');print('\n'.join(parts))
