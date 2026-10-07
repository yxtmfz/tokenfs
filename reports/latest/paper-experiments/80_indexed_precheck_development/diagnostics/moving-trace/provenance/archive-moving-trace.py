#!/usr/bin/env python3
"""Append completed diagnostic evidence; preserve primary80 evidence/results."""
from pathlib import Path
import hashlib,json,shutil,tarfile

ROOT=Path(__file__).resolve().parent;WORK=ROOT.parent
REPORT=WORK/'tokenfs-eval/reports/latest/paper-experiments/80_indexed_precheck_development'
DEST=REPORT/'diagnostics/moving-trace'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda p:json.loads(p.read_text())
def dump(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def hashes(folder):return {str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
def copy(source,target):target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)

assert not DEST.exists()
protected={str(p.relative_to(REPORT)):sha(p) for folder in [REPORT/'data',REPORT/'validation/results'] for p in folder.rglob('*') if p.is_file()}
for name in ['source.tar.gz','source-hashes.json','evidence.tar.gz']:
    p=REPORT/'provenance'/name;protected[str(p.relative_to(REPORT))]=sha(p)
raw=ROOT/'moving-trace-evidence';raw_hashes=hashes(raw)
assert len(raw_hashes)==27 and not list(raw.rglob('state.db-*'))
assert raw_hashes==load(ROOT/'moving-trace-inputhashes-independent.json')
raw_tar=ROOT/'moving-trace-evidence.tar.gz'
assert sha(raw_tar)=='c71dec53662c741e0423814c8a8ff050a34ce97094f81dcd448d7a789e2e7fb1'
with tarfile.open(raw_tar) as handle:
    members=[m for m in handle.getmembers() if m.isfile()]
    assert len(members)==27 and {m.name:hashlib.sha256(handle.extractfile(m).read()).hexdigest() for m in members}==raw_hashes
audit=load(ROOT/'moving-trace-audit-root.json')
assert audit==load(ROOT/'moving-trace-audit-independent.json') and audit['passed'] and audit['diagnosis_only'] and not audit['performance_evidence']
assert audit['source_files_checked']==355 and all(a['requests']==1152 and a['event_count']==9408 and a['dropped']==0 and a['passed'] for a in audit['arms'].values())
outputs=hashes(ROOT/'moving-trace-review-root')
assert len(outputs)==7 and outputs==hashes(ROOT/'moving-trace-review-independent')
shutil.copytree(raw,DEST/'data');shutil.copytree(ROOT/'moving-trace-review-root',DEST/'review')
copy(raw_tar,DEST/'provenance/evidence.tar.gz')
for name in ['moving-trace-audit-root.json','moving-trace-audit-independent.json','moving-trace-inputhashes-independent.json',
             'launch-moving-trace.sh','launch-moving-trace.log','collect-moving-trace.sh','collect-moving-trace.log']:
    copy(ROOT/name,DEST/'provenance'/name)
copy(Path(__file__),DEST/'provenance/archive-moving-trace.py')
tool_archive=WORK/'hotspot-indexed80-moving-trace-tools.tar.gz';tool_manifest=WORK/'hotspot-indexed80-moving-trace-tools-manifest.json'
manifest=load(tool_manifest)
assert sha(tool_archive)==manifest['archive_sha256']=='540c7eddf7362313aca0dccf1b4cbe62d17e770ceb433e7503038a3f5b5c87c7'
copy(tool_archive,DEST/'provenance/frozen-tools.tar.gz');copy(tool_manifest,DEST/'provenance/frozen-tools-manifest.json')
with tarfile.open(tool_archive) as handle:
    seen=set()
    for member in handle.getmembers():
        name=Path(member.name)
        assert member.isfile() and not name.is_absolute() and '..' not in name.parts and member.name not in seen
        seen.add(member.name);target=DEST/'tools'/member.name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(handle.extractfile(member).read())
assert hashes(DEST/'tools')=={m['path']:m['sha256'] for m in manifest['members']} and len(manifest['members'])==12
dump(DEST/'provenance/agreement.json',dict(passed=True,audit_json_equal=True,analysis_byte_identical=True,
    analysis_files=outputs,raw_files=raw_hashes,requests=2304,diagnosis_only=True,performance_evidence=False))
dump(DEST/'provenance/protected-primary80-hashes.json',protected)
fuse=WORK/'hotspot-fuse-read-review';fuse_dest=REPORT/'diagnostics/fuse-read-review';fuse_hashes={}
for name in ['README.md','analyze.py','evidence.json','moving-trace-independent-review.md','moving-trace-reviewed-files.json',
             'fuse3-package/usr/include/fuse3/fuse_common.h','fuse3-package/usr/share/doc/libfuse3-dev/copyright']:
    copy(fuse/name,fuse_dest/name);fuse_hashes[name]=sha(fuse/name)
copy(WORK/'affinity-shared-preflight-cn7.json',fuse_dest/'historical-affinity-shared-preflight-cn7.json')
fuse_hashes['historical-affinity-shared-preflight-cn7.json']=sha(WORK/'affinity-shared-preflight-cn7.json')
dump(fuse_dest/'copied-files.json',dict(files=fuse_hashes,source_scope='historical77 traces; frozen80 source; saved historical kernel receipt; upstream version interpretation',
    no_binary_package_or_library_copied=True,no_fresh_kernel_query=True))
reviewed=load(fuse_dest/'moving-trace-reviewed-files.json')
assert all(sha(DEST/'tools'/name)==value for name,value in reviewed.items())
assert all(sha(REPORT/name)==value for name,value in protected.items())
print(json.dumps(dict(added_diagnostic_requests=2304,raw_files=27,tool_files=12,primary80_unchanged=True,analysis_outputs_equal=7,
    remaining='Write actual-execution README, extend archive verifier, refresh inventory.')))
