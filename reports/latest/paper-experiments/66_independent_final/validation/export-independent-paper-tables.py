from pathlib import Path
import json
w=Path(__file__).resolve().parent;s=json.loads((w/'independent-final-summary.json').read_text())
labels={'moving_shared':'Moving hotspots','public_toolagent':'Public trace replay','stationary_shared':'Stationary hotspots','uniform':'Uniform random'}
titles=[('Hotspot valuation ablation','NoHotspot'),('Logical-domain placement ablation','NoAffinity'),('Victim-loss-aware admission ablation','NoJoint'),('Overall Full versus shared SIEVE','PoolSIEVE1')]
lines=['% Requires \\usepackage{booktabs}. Rates are aggregate logical MiB/s; p99 values are medians of run-level percentiles.','% Independent inputs, same frozen binary. Negative results and untriggered mechanisms remain in the report.']
for i,(title,base) in enumerate(titles,1):
 lines.extend(['\\begin{table*}[t]','\\centering','\\caption{'+title+'. p99 columns show the median of run-level p99 values, not a pooled percentile.}',f'\\label{{tab:tokenfs-independent-{i}}}','\\begin{tabular}{lrrrrrrr}','\\toprule','Workload & $n$ & Full (MiB/s) & Control (MiB/s) & Gain (\\%) & Full p99 (ms) & Control p99 (ms) & Strict passes \\\\','\\midrule'])
 for r in s['rows']:
  if r['baseline']!=base:continue
  lines.append(f"{labels[r['scenario']]} & {r['n']} & {r['full_mib_s']:.3f} & {r['baseline_mib_s']:.3f} & {r['aggregate_gain_pct']:+.3f} & {r['full_p99_median_ms']:.3f} & {r['baseline_p99_median_ms']:.3f} & {r['strict_passes']}/{r['n']} \\\\")
 lines.extend(['\\bottomrule','\\end{tabular}','\\end{table*}',''])
(w/'independent-final-four-tables.tex').write_text('\n'.join(lines))
