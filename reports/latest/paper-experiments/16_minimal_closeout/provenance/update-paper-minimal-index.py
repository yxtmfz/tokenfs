from pathlib import Path
import json
w=Path(__file__).resolve().parent;r=w/'tokenfs-eval';v=json.loads((r/'reports/latest/paper-experiments/16_minimal_closeout/verdict.json').read_text())
for rel in ['README.md','docs/experiments.md','docs/claim-evidence-ledger.md','docs/evidence-experiments.md']:
 p=r/rel;s=p.read_text();assert '16_minimal_closeout' not in s
 prefix='' if rel=='README.md' else '../'
 line=(f"> 最新最小补实验：[同版本整体速度、H/J 消融与论文边界]({prefix}reports/latest/paper-experiments/16_minimal_closeout/README.md)。"
       f"完成 336 次正式测速、56 项内容检查、28 次开发测速和 12 次描述性边界测速；16 项整体缓存比较中，确认提速 {len(v['primary_faster'])} 项、确认变慢 {len(v['primary_slower'])} 项、未确定 {len(v['primary_uncertain'])} 项。"
       "五个实验亲和开关关闭，共享旧元数据统计仍保留。下方历次结果按各自版本解释，不混算；GPU 亲和和真实推理收益仍未证实。\n\n")
 pos=s.index('\n\n')+2;s=s[:pos]+line+s[pos:]
 if rel=='docs/experiments.md':s=s.replace('> 当前结果：[三项机制','> 历史综合结果：[三项机制',1)
 if rel=='README.md':s=s.replace('：最新统一结果报告。','：第一轮历史结果报告。')
 p.write_text(s)
