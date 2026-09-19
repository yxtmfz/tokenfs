#!/usr/bin/env python3
"""Exercise every ablation against directory-backed canonical data; NOT a speed benchmark."""
import argparse
from pathlib import Path
import random

from evidence_benchmark import MIB, SCENARIOS, STRATEGIES, dump, run_case, sha, trace_for


def main():
    p=argparse.ArgumentParser();p.add_argument("--binary",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();root=a.output.resolve();root.mkdir(parents=True,exist_ok=False)
    canonical=root.parent/(root.name+"-canonical");canonical.mkdir(exist_ok=False)
    remote_run=canonical/("eval-"+root.name);remote_run.mkdir()
    args=dict(output=str(root),remote_root=str(canonical),requests=48,shard_mib=2,quota_mib=4,
              scenarios=SCENARIOS,strategies=list(STRATEGIES),seeds=[37],backend_direct=True,verify=True,profile="custom")
    dump(root/"manifest.json",dict(args=args,binary_sha256=sha(a.binary),
                                  cache_mode="directory-backed correctness only; never performance evidence"))
    for scenario in SCENARIOS:
        block=root/f"{scenario}-seed-37";block.mkdir()
        data=remote_run/block.name;(data/"gpu0").mkdir(parents=True)
        sizes,events=trace_for(scenario,37,48,2);expected={}
        for key,mib in sizes.items():
            path=data/"gpu0"/f"shard-{key:06d}.tokens"
            with path.open("wb") as f:
                for _ in range(mib):f.write(bytes([key+1])*MIB)
            expected[str(key)]=sha(path)
        dump(block/"trace.json",events);dump(block/"objects.json",dict(sizes_mib=sizes,sha256=expected))
        order=list(STRATEGIES);random.Random(37).shuffle(order);dump(block/"order.json",order)
        for strategy in order:
            run_case(a.binary.resolve(),block/strategy,data,strategy,events,expected,4,True,True)
            print(f"PASS {scenario} {strategy}",flush=True)
    from evidence_audit import audit
    if not audit(root)["passed"]:raise RuntimeError("matrix audit failed")


if __name__=="__main__":main()
