from pathlib import Path
import json,hashlib,subprocess,zipfile
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';out=w.parent/'outputs';report=r/'reports/latest/paper-experiments/15_affinity_handover'
read=lambda p:json.loads(p.read_text())
assert read(report/'validation/independent-audit.json')['passed']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=r,text=True).strip()
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip();ci=read(w/'affinity-v3-final-ci.json');assert ci['head_sha']==revision and ci['conclusion']=='success'
text=(report/'README.md').read_text();base='https://github.com/yxtmfz/tokenfs/blob/'+revision+'/'
for folder in ['confirmation','validation']:text=text.replace(']('+folder+'/',']('+base+'reports/latest/paper-experiments/15_affinity_handover/'+folder+'/')
for name in ['mechanism-summary.json','drain-review.json']:text=text.replace(']('+name+')',']('+base+'reports/latest/paper-experiments/15_affinity_handover/'+name+')')
text=text.replace('](../14_affinity_refinement/',']('+base+'reports/latest/paper-experiments/14_affinity_refinement/').replace('](../../../../',']('+base)
text+='\n[代码与完整证据 PR #4](https://github.com/yxtmfz/tokenfs/pull/4)，未合并。\n'
(out/'TokenFS创新点二优化与最终实验表.md').write_text(text)
files={}
for folder in ['14_affinity_refinement','15_affinity_handover']:
 for p in (r/'reports/latest/paper-experiments'/folder).rglob('*'):
  if p.is_file():files[str(p.relative_to(r))]=p
for rel in ['scripts/affinity_v3_evidence.py','scripts/affinity_v3_study.py','scripts/affinity_joint_study.py','scripts/evidence_benchmark.py','scripts/evidence_report.py','scripts/evidence_audit.py','scripts/measured_study.py','src/main.cpp','src/measured_policy.h','study-configs/affinity-v3-freeze-01.json','study-configs/affinity-v3-confirmation-01.json','study-configs/affinity-v3-public-windows.json','study-configs/affinity-v2-public-windows.json','study-configs/affinity-joint-public-windows.json','study-configs/measured-b3-freeze.json','docs/affinity-v3-plan.md','docs/affinity-v2-plan.md']:files[rel]=r/rel
files['public-source/toolagent_trace.jsonl']=w/'public-traces/toolagent_trace.jsonl';files['validation/github-ci.json']=w/'affinity-v3-final-ci.json';files['REPRODUCE.py']=w/'reproduce-affinity-bundle.py'
readme='''# TokenFS 创新点二：最终实测速率与完整证据

入口：reports/latest/paper-experiments/15_affinity_handover/README.md。
本版 288 次正式测速、48 项内容检查和 48 次开发测速；首轮 D 的 288 次未确认独立提速结果及全部 A/B/C/D 开发记录保留在报告 14。两轮正式数据不能混算，也不能把修复旧版当作独立收益。

Python 3.12+，无需 GPU、服务器或第三方库，解压后执行：

```bash
python3 REPRODUCE.py --output /tmp/tokenfs-affinity-reproduction.json
```

脚本先校验 PACKAGE-MANIFEST.json 的全部文件哈希，再独立复算两轮共 576 次正式实验。首轮严格使用其冻结源码包，当前轮使用本包根目录源码；全部操作离线。A/B/C 开发版本另保留源码、原始归档和已完成的独立审计。

本次优化共保留 234 次开发测速、234 项内容检查以及两轮共 576 次正式测速；只有报告 15 的新确认样本用于本版性能结论。速率是实际存储读取 MiB/s，不是物理 GPU 或推理 tokens/s。包内服务器路径仅为来源记录，不含 SSH 配置或凭据。
'''
content={name:p.read_bytes() for name,p in files.items()};content['README.md']=readme.encode()
manifest={name:hashlib.sha256(value).hexdigest() for name,value in content.items()}
archive=out/'TokenFS创新点二优化完整证据包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,value in sorted(content.items()):z.writestr(name,value)
 z.writestr('PACKAGE-MANIFEST.json',json.dumps(dict(git_revision=revision,files=manifest),ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
status=dict(git_revision=revision,pr_url='https://github.com/yxtmfz/tokenfs/pull/4',merged=False,ci=ci,experiment=read(report/'verdict.json'),archive=dict(name=archive.name,bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
(out/'TokenFS创新点二优化交付状态.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n');print(json.dumps(status,ensure_ascii=False))
