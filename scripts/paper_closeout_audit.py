#!/usr/bin/env python3
"""Re-extract and re-audit the frozen B3 evidence offline; never run benchmarks.

Requires Python 3.12+ and the pinned Mooncake source files. All derived writes go
to a temporary directory; the original archive, report and SHA256SUMS stay intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trace-dir', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    report = repo / 'reports/latest/paper-experiments/11_measured_admission'
    freeze = read(repo / 'study-configs/measured-b3-freeze.json')
    verified = []
    for line in (report / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split('  ', 1)
        path = report / name
        require(path.resolve().is_relative_to(report.resolve()), 'hash path escapes report')
        require(path.is_file() and sha(path) == digest, 'changed report file: ' + name)
        require(name not in verified, 'duplicate hash entry: ' + name)
        verified.append(name)
    actual = {str(p.relative_to(report)) for p in report.rglob('*')
              if p.is_file() and p.name != 'SHA256SUMS'}
    require(actual == set(verified), 'hash manifest does not cover exact report file set')
    runtime = {}
    for name in ['src/main.cpp', 'src/measured_policy.h', 'scripts/measured_study.py',
                 'scripts/evidence_benchmark.py', 'scripts/measured_domain_study.py']:
        runtime[name] = sha(repo / name)
        require(runtime[name] == freeze['hashes'][name], 'current runtime differs: ' + name)

    commands = []
    def run(script, *arguments):
        command = [sys.executable, str(repo / 'scripts' / script), *map(str, arguments)]
        result = subprocess.run(command, cwd=repo, text=True, capture_output=True)
        require(result.returncode == 0, script + ' failed: ' + result.stdout + result.stderr)
        commands.append({'script': script, 'returncode': result.returncode})
        print('PASS', script, flush=True)

    with tempfile.TemporaryDirectory(prefix='tokenfs-closeout-') as temp:
        base = Path(temp)
        archives = {}
        for filename, destination in [
            ('cn7-measured-final-evidence.tar.gz', base),
            ('measured-b3-cn8-validation-evidence.tar.gz', base / 'cn8')]:
            source = report / 'raw' / filename
            destination.mkdir(exist_ok=True)
            with tarfile.open(source) as archive:
                members = archive.getmembers()
                names = [m.name for m in members]
                require(len(names) == len(set(names)), 'duplicate archive member')
                require(all(m.isfile() and not Path(m.name).is_absolute()
                            and '..' not in Path(m.name).parts for m in members),
                        'unsafe or non-regular archive member')
                archive.extractall(destination, filter='data')
            archives[filename] = {'sha256': sha(source), 'regular_files': len(members)}

        cn7 = base / 'cn7'
        reproduced = []
        performance = []
        for batch, expected in [('measured-confirm-02', 648),
                                ('measured-supplement-02', 96),
                                ('measured-domain-supplement-01', 12)]:
            root = cn7 / batch
            files = ['summary.json']
            if batch == 'measured-domain-supplement-01':
                run('measured_domain_study.py', 'report', '--output', root)
            else:
                files += ['paired-comparisons.json', 'component-evidence.json',
                          'interactions.json', 'mechanisms.json', 'segments.json']
                run('measured_artifacts.py', root)
            audit = read(root / 'batch-audit.json')
            require(audit['passed'] and audit['checked_runs'] == audit['expected_runs'] == expected,
                    'incomplete performance batch')
            performance.append({'batch': batch, 'runs': expected, 'passed': True})
            for name in files:
                require(read(root / name) == read(report / batch / name),
                        'recomputed JSON differs: ' + batch + '/' + name)
                reproduced.append(batch + '/' + name)

        content = []
        for host in ['cn7', 'cn8']:
            root = base / host / 'measured-correctness-03'
            run('measured_study.py', 'audit', '--output', root)
            audit = read(root / 'batch-audit.json')
            require(audit['passed'] and audit['checked_runs'] == audit['expected_runs'] == 65,
                    'incomplete content audit')
            content.append({'host': host, 'batch': root.name, 'runs': 65, 'passed': True})
        root = base / 'cn8' / 'measured-multidomain-02'
        run('measured_multidomain_check.py', '--audit', '--output', root)
        audit = read(root / 'batch-audit.json')
        require(audit['passed'] and audit['checked_runs'] == audit['expected_runs'] == 39,
                'incomplete multidomain audit')
        content.append({'host': 'cn8', 'batch': root.name, 'runs': 39, 'passed': True})
        run('measured_freeze_audit.py', '--evidence-root', cn7,
            '--trace-dir', args.trace_dir.resolve())
        provenance = read(cn7 / 'measured-b3-independent-provenance-audit.json')
        require(provenance['passed'] and provenance['checked_performance_cases'] == 756
                and provenance['checked_public_windows'] == 30, 'provenance audit incomplete')

        # Independently recalculate logical bytes / foreground duration and paired
        # geometric time ratios directly from per-run results, not published means.
        root = cn7 / 'measured-confirm-02'
        spec = read(root / 'manifest.json')['spec']
        comparisons = read(root / 'paired-comparisons.json')
        ratio_checks = []
        for row in comparisons:
            logs = []
            for block in spec['blocks']:
                if block['scenario'] != row['scenario'] or row['baseline'] not in block['variants']:
                    continue
                full = read(root / block['id'] / 'AURA-adaptive/result.json')
                reference = read(root / block['id'] / row['baseline'] / 'result.json')
                logs.append(math.log(full['job_wall_s'] / reference['job_wall_s']))
            require(len(logs) == row['n'], 'paired sample count differs')
            ratio = math.exp(sum(logs) / len(logs))
            require(math.isclose(ratio, row['time_ratio'], rel_tol=1e-12), 'paired ratio differs')
            ratio_checks.append({'scenario': row['scenario'], 'baseline': row['baseline'], 'passed': True})
        valid_resources = 0
        for batch in performance:
            for path in (cn7 / batch['batch']).glob('*/*/result.json'):
                result = read(path)
                require(math.isclose(result['effective_mib_s'],
                        result['logical_bytes'] / 1048576 / result['job_wall_s'], rel_tol=1e-12),
                        'actual throughput formula differs')
                for key in ['daemon_cpu_s', 'daemon_peak_rss_kib', 'request_p50_s', 'request_p99_s']:
                    value = result[key]
                    require(isinstance(value, (int, float)) and math.isfinite(value) and value >= 0,
                            'invalid resource/latency field: ' + key)
                valid_resources += 1
        primary = [r for r in comparisons if r['baseline'] in ['LRU-equal', 'LFU-equal', 'RecentLFU-admit']]
        verdicts = {name: sum(r['verdict'] == name for r in primary)
                    for name in ['faster', 'slower', 'uncertain']}
        # Keep the published verdict vocabulary explicit, including uncertainties.
        require(len(primary) == 21 and verdicts == {'faster': 12, 'slower': 0, 'uncertain': 9},
                'unexpected primary outcomes')
        result = dict(passed=True, audit_kind='offline re-extraction and reproduction; no new performance runs',
            report_files_verified=len(verified), archives=archives, runtime_source_sha256=runtime,
            performance_batches=performance, content_batches=content,
            reproduced_json_files=reproduced, all_reproduced_values_exactly_equal=True,
            independent_primary_and_component_ratio_checks=len(ratio_checks),
            valid_throughput_resource_latency_records=valid_resources,
            provenance=provenance, primary_comparisons=primary, commands=commands,
            all_original_paper_claims_verified=False,
            gpu_affinity_independent_performance_verified=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ['passed', 'report_files_verified',
          'independent_primary_and_component_ratio_checks', 'valid_throughput_resource_latency_records']}))


if __name__ == '__main__':
    main()
