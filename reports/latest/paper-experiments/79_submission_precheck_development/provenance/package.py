import json,sys,tarfile,tempfile,subprocess,hashlib
from pathlib import Path
sys.path.insert(0,'scripts')
import submission_precheck_hpj_study as s
out=Path('../hotspot-precheck79');paths=s.SOURCES
hashes={p:s.sha(Path(p)) for p in paths}
(out/'source-hashes.json').write_text(json.dumps(hashes,indent=2)+'\n')
with tarfile.open(out/'source.tar.gz','w:gz') as t:
 for p in paths:t.add(p,arcname=p)
with tempfile.TemporaryDirectory(dir=out) as d:
 with tarfile.open(out/'source.tar.gz') as t:t.extractall(d)
 r=subprocess.run(['python3','-m','unittest','discover','-s','tests','-p','*_test.py'],cwd=d,capture_output=True,text=True)
 (out/'standalone-tests.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stdout+r.stderr
print(len(paths),'frozen files; standalone Python passed;',hashlib.sha256((out/'source.tar.gz').read_bytes()).hexdigest())
