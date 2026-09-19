#!/usr/bin/env python3
"""Publication-exportable plots from audited measurements (Matplotlib required)."""
import argparse
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from evidence_audit import audit
from evidence_report import interval


def figures(root, output):
    if not audit(root)["passed"]: raise ValueError("incomplete/invalid batch")
    output.mkdir(parents=True,exist_ok=True)
    rows=[]
    for p in root.glob("*-seed-*/*/result.json"):
        r=json.loads(p.read_text())
        if r["verify_every_request"]:raise ValueError("verification is not performance evidence")
        r["scenario"]=p.parent.parent.name.split("-seed-")[0];rows.append(r)
    scenarios=[s for s in ["stable","scan","mixed","shared_shift","uniform"] if any(r["scenario"]==s for r in rows)]
    strategies=["RemoteOnly","LRU-equal","LFU-equal","AURA-core"]
    colors=["#9CA3AF","#60A5FA","#A78BFA","#0F766E"]
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"savefig.dpi":180})
    fig,ax=plt.subplots(figsize=(10,4.8))
    width=.19
    for j,(strategy,color) in enumerate(zip(strategies,colors)):
        for i,scenario in enumerate(scenarios):
            values=[r["effective_mib_s"] for r in rows if r["strategy"]==strategy and r["scenario"]==scenario]
            if not values:continue
            mean=statistics.mean(values);lo,hi=interval(values)
            ax.bar(i+(j-1.5)*width,mean,width,color=color,label=strategy if i==0 else None)
            if lo is not None:ax.errorbar(i+(j-1.5)*width,mean,yerr=[[max(0,mean-lo)],[max(0,hi-mean)]],color="#1F2937",capsize=2,lw=1)
    ax.set_xticks(range(len(scenarios)),[s.replace("_"," ") for s in scenarios])
    ax.set_ylabel("Effective throughput (MiB/s); higher is faster")
    ax.set_title(f"{root.name}: identical work within each paired block",loc="left",fontweight="bold")
    ax.legend(ncol=4,frameon=False,loc="upper center",bbox_to_anchor=(.5,1.0))
    ax.set_ylim(0,ax.get_ylim()[1]*1.18);ax.grid(axis="y",alpha=.15);ax.set_axisbelow(True)
    fig.text(.08,.02,"Client O_DIRECT; target caches uncontrolled. Bars: mean; whiskers: block-bootstrap 95% CI.",fontsize=8)
    fig.tight_layout(rect=(0,.05,1,1))
    for ext in ["png","pdf","svg"]:fig.savefig(output/f"throughput.{ext}")
    plt.close(fig)
    comparisons=json.loads((root/"paired-comparisons.json").read_text())
    selected=[r for r in comparisons if r["baseline"] not in {"RemoteOnly","LRU-equal","LFU-equal"}]
    fig,ax=plt.subplots(figsize=(10,max(4,len(selected)*.32+1.2)))
    for i,r in enumerate(selected):
        mean=r["time_ratio"];lo,hi=r["ci95"]
        color="#0F766E" if r["verdict"]=="支持此场景下真实提速" else "#B91C1C" if r["verdict"]=="此场景下更慢" else "#64748B"
        ax.plot(mean,i,"o",color=color,markersize=4)
        if lo is not None:ax.hlines(i,lo,hi,color=color,lw=1.5)
    ax.axvline(1,color="#111827",lw=1,linestyle="--")
    ax.set_yticks(range(len(selected)),[f"{r['scenario']} | {r['treatment']} / {r['baseline']}" for r in selected])
    ax.invert_yaxis();ax.set_xlabel("Paired geometric time ratio; below 1 is faster")
    ax.set_title(f"{root.name}: component ablations",loc="left",fontweight="bold")
    ax.grid(axis="x",alpha=.15)
    fig.text(.02,.012,"95% bootstrap intervals are unadjusted. Color uses predeclared family-wise Holm tests; gray = inconclusive/pilot.",fontsize=8)
    fig.tight_layout(rect=(0,.05,1,1))
    for ext in ["png","pdf","svg"]:fig.savefig(output/f"ablations.{ext}")
    plt.close(fig)


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("root",type=Path);p.add_argument("output",type=Path)
    a=p.parse_args();figures(a.root,a.output)
