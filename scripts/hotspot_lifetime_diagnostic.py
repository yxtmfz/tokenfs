#!/usr/bin/env python3
"""Four fixed diagnostic runs; timings with tracing are not confirmation results."""
import argparse
import json
import os
import random
from pathlib import Path
from evidence_benchmark import MIB, dump, run_case, sha
from measured_study import check_mount
from integrated_hpj_cohort_caller_final_study import configuration, trace


def run(binary, output, remote):
    binary, output, remote = binary.resolve(), output.resolve(), remote.resolve()
    identity = check_mount(remote, False)
    output.mkdir(parents=True, exist_ok=False)
    data_root = remote / 'hotspot-lifetime-73'
    data_root.mkdir(exist_ok=False)
    specs = [('moving_shared', 74801, ['Full', 'NoHotspot']),
             ('public_toolagent', 74802, ['NoHotspot', 'Full'])]
    repo = Path(__file__).resolve().parents[1]
    freeze = json.loads((repo / 'diagnostic-source-hashes.json').read_text())
    assert all(sha(repo / p) == h for p, h in freeze.items())
    dump(output / 'manifest.json', dict(purpose='diagnosis_only', specs=specs,
         source_hashes=freeze, binary_sha256=sha(binary), **identity))
    for scene, seed, order in specs:
        block = output / scene
        block.mkdir()
        data = data_root / scene
        (data / 'gpu0').mkdir(parents=True)
        events = trace(dict(scenario=scene, seed=seed, requests=1152, shard_mib=2))
        assert len(events) == 1152
        expected = {}
        for key in sorted({e['key'] for e in events}):
            path = data / 'gpu0' / f'shard-{key:06d}.tokens'
            payload = random.Random(seed * 100000 + key).randbytes(MIB)
            with path.open('wb') as f:
                f.write(payload * 2)
                f.flush()
                os.fsync(f.fileno())
            expected[str(key)] = sha(path)
        dump(block / 'trace.json', events)
        dump(block / 'objects.json', expected)
        for arm in order:
            case = block / arm
            cfg = configuration(arm, case, data, 24, True)
            cfg['policy']['request_trace_path'] = str(case / 'request-trace.json')
            run_case(binary, case, data, arm, events, expected, 24, False, True, configuration=cfg)
            result = json.loads((case / 'result.json').read_text())
            assert result['status'] == 'ok'
            print(json.dumps(dict(scene=scene, arm=arm, status='complete')), flush=True)
    assert all(sha(repo / p) == h for p, h in freeze.items())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--remote', type=Path, required=True)
    a = p.parse_args()
    run(a.binary, a.output, a.remote)
