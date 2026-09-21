from pathlib import Path
import json,hashlib,subprocess,zipfile
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';out=w.parent/'outputs';report=r/'reports/latest/paper-experiments/16_minimal_closeout'
read=lambda p:json.loads(p.read_text())
assert read(report/'validation/independent-audit.json')['passed']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=r,text=True).strip()
revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip();ci=read(w/'paper-minimal-final-ci.json');assert ci['head_sha']==revision and ci['conclusion']=='success'
text=(report/'README.md').read_text();base='https://github.com/yxtmfz/tokenfs/blob/'+revision+'/'
for folder in ['confirmation','validation']:text=text.replace(']('+folder+'/',']('+base+'reports/latest/paper-experiments/16_minimal_closeout/'+folder+'/')
text=text.replace('](phase-review.json)',']('+base+'reports/latest/paper-experiments/16_minimal_closeout/phase-review.json)').replace('](drain-review.json)',']('+base+'reports/latest/paper-experiments/16_minimal_closeout/drain-review.json)').replace('](../15_affinity_handover/',']('+base+'reports/latest/paper-experiments/15_affinity_handover/').replace('](../../../../',']('+base)
text+='\n[代码与完整证据 PR #5](https://github.com/yxtmfz/tokenfs/pull/5)，未合并。\n'
(out/'TokenFS最小补实验最终结果与论文论点.md').write_text(text)
subprocess.run([__import__('sys').executable,str(w/'export-paper-minimal-tex.py'),'--report',str(report),'--output',str(out/'TokenFS最小补实验四表.tex')],check=True)
files={str(p.relative_to(r)):p for p in report.rglob('*') if p.is_file()}
import sys
sys.path.insert(0,str(r/'scripts'));from paper_minimal_study import SOURCES
rels=SOURCES+['scripts/paper_minimal_evidence.py','study-configs/paper-minimal-freeze-01.json','study-configs/affinity-v3-public-windows.json','study-configs/affinity-v2-public-windows.json','study-configs/affinity-joint-public-windows.json','study-configs/measured-b3-freeze.json','docs/paper-minimal-plan.md','docs/paper-minimal-protocol-notes.md']
rels += [str(p.relative_to(r)) for p in (r/'study-configs').glob('paper-minimal-*.json')]
for rel in rels:files[rel]=r/rel
files['tables.tex']=out/'TokenFS最小补实验四表.tex'
files['public-source/toolagent_trace.jsonl']=w/'public-traces/toolagent_trace.jsonl';files['validation/github-ci.json']=w/'paper-minimal-final-ci.json';files['REPRODUCE.py']=w/'reproduce-paper-minimal.py'
readme='''# TokenFS 最小补实验完整证据

入口：reports/latest/paper-experiments/16_minimal_closeout/README.md。
336 次正式测速、56 项内容检查、28 次开发测速、12 次描述性边界测速。H+J 存储策略，实验亲和开关关闭；共享的旧元数据统计仍保留，见协议解释说明。实际 MiB/s，不是 GPU 或推理性能。

Python 3.12+，无需服务器、GPU 或第三方包，解压后执行：

```bash
python3 REPRODUCE.py --output /tmp/tokenfs-minimal-reproduction.json
```

脚本先验证 PACKAGE-MANIFEST.json 中的全部文件哈希，再从原始记录审计各批次、来源、配置、字节、时间线和统计，并检查故意篡改会被拒绝。离线复算不会重新执行服务器测速。

本包只复算本轮；旧报告和亲和失败结果保留在 GitHub 与已交付的旧证据包，不混用当前源码审计旧结果。服务器路径仅为来源，不含 SSH 配置、密码或私钥。
'''
content={name:p.read_bytes() for name,p in files.items()};content['README.md']=readme.encode()
manifest={name:hashlib.sha256(value).hexdigest() for name,value in content.items()}
archive=out/'TokenFS最小补实验完整证据包.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name,value in sorted(content.items()):z.writestr(name,value)
 z.writestr('PACKAGE-MANIFEST.json',json.dumps(dict(git_revision=revision,files=manifest),ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for name,h in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==h
status=dict(git_revision=revision,pr_url='https://github.com/yxtmfz/tokenfs/pull/5',merged=False,ci=ci,experiment=read(report/'verdict.json'),archive=dict(name=archive.name,bytes=archive.stat().st_size,sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
(out/'TokenFS最小补实验交付状态.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n');print(json.dumps(status,ensure_ascii=False))
