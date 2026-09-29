set -eu
. /home/wjxt/aura-kv-tools/env.sh
if pgrep -u "$(id -u)" -x tokenfs >/dev/null; then echo 'Existing own TokenFS process'; exit 2; fi
cd /home/wjxt/projects/tokenfs-integrated-hpj-cohort-caller-object-20260929
python3 - <<'PYCONTENT'
import sys,argparse
from pathlib import Path
sys.path.insert(0,'scripts')
import integrated_hpj_correctness as c
import integrated_hpj_cohort_caller_object_study as s
s.VARIANTS=[v for v in s.VARIANTS if v!='OldFull']
c.run(argparse.Namespace(study='integrated_hpj_cohort_caller_object_study',binary=Path('build-release/tokenfs'),freeze=Path('study-configs/integrated-hpj-cohort-caller-object-freeze.json'),output=Path('/home/wjxt/tokenfs-integrated-hpj-cohort-caller-object-evidence/correctness'),remote_root=Path('/srv/tokenfs/remote-cn7/integrated-hpj-cohort-caller-object-20260929')))
PYCONTENT
