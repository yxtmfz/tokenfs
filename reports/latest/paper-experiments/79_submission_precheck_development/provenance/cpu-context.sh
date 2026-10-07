set -eu
python3 - <<'PY'
import os,json
from pathlib import Path
allowed=sorted(os.sched_getaffinity(0));print('allowed_cpus',allowed)
out=[]
for cpu in allowed:
 p=Path('/sys/devices/system/cpu')/f'cpu{cpu}'
 def read(s):
  f=p/s
  return f.read_text().strip() if f.exists() else None
 out.append(dict(cpu=cpu,core=read('topology/core_id'),package=read('topology/physical_package_id'),siblings=read('topology/thread_siblings_list'),governor=read('cpufreq/scaling_governor')))
print(json.dumps(out));print('loadavg',os.getloadavg())
PY
