#!/usr/bin/env python3
"""Isolated Linux FUSE correctness checks, never performance evidence."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import errno
import hashlib
import json
import os
import random
from pathlib import Path
import sqlite3
import subprocess
import time

from evidence_benchmark import MIB, config_for, drain, dump, sha


def run(binary, root):
    root.mkdir(parents=True, exist_ok=False)
    remote=root/"canonical"; (remote/"gpu0"/"empty").mkdir(parents=True)
    case=root/"case";case.mkdir();mount=case/"mnt";mount.mkdir()
    cfg=config_for("LRU-equal",case,remote,4,True)
    dump(case/"config.json",cfg)
    expected={}
    for i in range(8):
        path=remote/"gpu0"/f"shard-{i:06d}.tokens"
        # Unique bytes across offsets catch repeated/shifted-block read bugs.
        path.write_bytes(random.Random(500+i).randbytes(2*MIB+(123 if i==0 else 0)))
        expected[path.name]=sha(path)
    checks=[]
    proc=None; log=None

    def start():
        nonlocal proc,log
        log=(root/"daemon.log").open("a")
        proc=subprocess.Popen([str(binary),"--config",str(case/"config.json"),"-f",str(mount)],stdout=log,stderr=log)
        deadline=time.monotonic()+15
        while not os.path.ismount(mount):
            if proc.poll() is not None or time.monotonic()>deadline: raise RuntimeError("mount failed")
            time.sleep(.02)

    def stop(abrupt=False):
        nonlocal proc,log
        if proc is None: return
        if abrupt:
            proc.kill();proc.wait(timeout=10)
            subprocess.run(["fusermount3","-uz",str(mount)],check=True)
        else:
            subprocess.run(["fusermount3","-u",str(mount)],check=True)
            proc.wait(timeout=120)
            if proc.returncode: raise RuntimeError(f"daemon exit {proc.returncode}")
        log.close();proc=None

    def read(key):
        path=mount/"gpu0"/f"shard-{key:06d}.tokens"
        if sha(path)!=expected[path.name]: raise RuntimeError("content mismatch")

    def canonical_unchanged():
        if {p.name:sha(p) for p in (remote/"gpu0").glob("*.tokens")} != expected:
            raise RuntimeError("canonical changed")

    try:
        start()
        target=mount/"gpu0"/"shard-000000.tokens"
        operations={
            "write-open":lambda:os.close(os.open(target,os.O_WRONLY)),
            "create":lambda:(mount/"gpu0"/"new.tokens").write_bytes(b"bad"),
            "truncate":lambda:os.truncate(target,0),
            "unlink":lambda:target.unlink(),
            "rename":lambda:target.rename(mount/"gpu0"/"changed.tokens"),
            "mkdir":lambda:(mount/"gpu0"/"new-dir").mkdir(),
            "rmdir":lambda:(mount/"gpu0"/"empty").rmdir(),
        }
        for name,operation in operations.items():
            try: operation()
            except OSError as exc:
                if exc.errno != errno.EROFS: raise
            else: raise RuntimeError(f"mutation unexpectedly accepted: {name}")
        canonical_unchanged();checks.append("seven mutations rejected with EROFS; canonical unchanged")
        original=(remote/"gpu0"/target.name).read_bytes()
        for phase in range(2):
            for offset in [0,1,4095,4096,MIB-1,2*MIB,len(original)-1,len(original),len(original)+7]:
                for length in [0,1,17,4097,MIB+3]:
                    with target.open("rb",buffering=0) as f:
                        f.seek(offset)
                        if f.read(length)!=original[offset:offset+length]:
                            raise RuntimeError(f"range mismatch at {offset}+{length}")
            drain(case/"state.db")
        checks.append("unique-byte unaligned ranges, partial EOF and reads beyond EOF match canonical")
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(read,[i%8 for i in range(96)]))
        drain(case/"state.db")
        canonical_unchanged()
        for p in (case/"cache0").rglob("*.tokens"):
            if sha(p)!=expected[p.name]: raise RuntimeError("bad retained replica")
        if sum(p.stat().st_size for p in (case/"cache0").rglob("*") if p.is_file())>4*MIB:
            raise RuntimeError("retained quota")
        checks.append("96 concurrent full-hash reads; retained copies and final quota valid")
        stop();start()
        for i in range(8): read(i)
        drain(case/"state.db");canonical_unchanged()
        checks.append("graceful restart preserves all eight objects")
        # Kill only after drain: this checks metadata reopen, not in-flight crash atomicity.
        stop(abrupt=True);start()
        for i in range(8): read(i)
        drain(case/"state.db");canonical_unchanged()
        checks.append("idle SIGKILL/restart preserves all eight objects")
        stop()
        with sqlite3.connect(case/"state.db") as con:
            counters=dict(con.execute("SELECT name,value FROM metrics"))
        if any(v for k,v in counters.items() if k.endswith("error_count")):
            raise RuntimeError("daemon error metric")
        dump(root/"result.json",dict(passed=True,checks=checks,metrics=counters,binary_sha256=sha(binary),
                                    kernel=subprocess.check_output(["uname","-a"],text=True).strip(),
                                    limitations="Directory backend correctness only; no claim about mid-copy crash, power loss, peak occupancy or NVMe/TCP performance."))
    except Exception as exc:
        dump(root/"failure.json",dict(error=repr(exc),checks_completed=checks))
        raise
    finally:
        if proc is not None:
            subprocess.run(["fusermount3","-uz",str(mount)],capture_output=True)
            try:proc.wait(timeout=20)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
            log.close()


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--binary",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();run(a.binary.resolve(),a.output.resolve())
