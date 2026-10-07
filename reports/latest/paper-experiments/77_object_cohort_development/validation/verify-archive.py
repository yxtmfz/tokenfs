#!/usr/bin/env python3
"""Read-only archive hash verification. It does not execute model source."""
from pathlib import Path
import hashlib,json,tarfile
root=Path(__file__).resolve().parents[1]
sha=lambda data:hashlib.sha256(data).hexdigest()
load=lambda path:json.loads(path.read_text())
manifest=load(root/'archive-manifest.json')
actual={str(p.relative_to(root)):sha(p.read_bytes()) for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'archive-manifest.json' and '__pycache__' not in p.parts}
assert actual==manifest['files'],'archive inventory mismatch'
archives=load(root/'provenance/archive-hashes.json')['archives']
for name,receipt in archives.items():
    content=(root/'provenance'/name).read_bytes()
    assert len(content)==receipt['bytes'] and sha(content)==receipt['sha256'],name
expected=load(root/'provenance/data-hashes.json')
raw={str(p.relative_to(root/'data')):sha(p.read_bytes()) for p in (root/'data').rglob('*') if p.is_file()}
assert raw==expected and len(raw)==290,'raw data changed'
with tarfile.open(root/'provenance/evidence.tar.gz') as archive:
    names=[m.name for m in archive.getmembers() if m.isfile()]
    assert len(names)==len(set(names)),'duplicate archive path'
    stored={m.name:sha(archive.extractfile(m).read()) for m in archive.getmembers() if m.isfile()}
assert stored==raw,'raw archive mismatch'
models=load(root/'provenance/model-files.json')
for name,receipt in models.items():
    model=root/'models'/name
    copied={str(p.relative_to(model)):sha(p.read_bytes()) for p in model.rglob('*') if p.is_file()}
    assert copied==receipt['hashes'],name+' model files changed'
    assert all(p.suffix in ['.cpp','.h','.py','.json','.txt','.md'] for p in model.rglob('*') if p.is_file())
trace=root/'diagnostics/tail-trace'
status=load(trace/'status.json')
if status['status']=='complete_locally_audited':
    assert sha((trace/'evidence.tar.gz').read_bytes())==status['archive_sha256']
    trace_raw={str(p.relative_to(trace/'data')):sha(p.read_bytes()) for p in (trace/'data').rglob('*') if p.is_file()}
    assert trace_raw==load(trace/'data-hashes.json') and len(trace_raw)==27
    with tarfile.open(trace/'evidence.tar.gz') as archive:
        trace_stored={m.name:sha(archive.extractfile(m).read()) for m in archive.getmembers() if m.isfile()}
    assert trace_stored==trace_raw
review=load(root/'validation/results/review.json')
assert review['passed'] and review['full_acceptance_primary']==12 and review['primary_comparisons']==16 and not review['primary_all_passed']
print(json.dumps(dict(passed=True,archive_files=len(actual),raw_files=len(raw),primary_passed=12,primary_total=16,all_primary_passed=False)))
