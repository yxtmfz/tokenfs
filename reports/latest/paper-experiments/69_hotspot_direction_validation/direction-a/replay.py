from pathlib import Path
import json,subprocess,tempfile
p=Path(__file__).resolve().parent
with tempfile.TemporaryDirectory() as t:
 binary=Path(t)/"replay"
 subprocess.run(["c++","-std=c++17","-O2","-I",str(p/"source"),str(p/"replay.cpp"),"-o",str(binary)],check=True)
 rows=[]
 for f in sorted((p/"inputs").glob("*.txt")):
  result=subprocess.check_output([str(binary),str(f),"prior"],text=True)
  rows.append(dict(input=f.stem,result=result.splitlines()))
 assert dict(speed_evidence=False,server_runs=0,rows=rows)==json.loads((p/"screen.json").read_text())
 print(json.dumps(dict(passed=True,inputs=len(rows),arms=len(rows)*4,speed_evidence=False)))
