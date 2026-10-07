#!/usr/bin/env python3
"""Preserve frozen development evidence; never replace a failed cell."""
from pathlib import Path
import hashlib,json,shutil,tarfile

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parent/'tokenfs-eval'
DEST=REPO/'reports/latest/paper-experiments/77_object_cohort_development'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def hashes(root):return {str(p.relative_to(root)):sha(p) for p in sorted(root.rglob('*')) if p.is_file()}

def main():
    DEST.mkdir(parents=True,exist_ok=False)
    for d in ['provenance','validation','models','diagnostics/tail-trace/tools']:(DEST/d).mkdir(parents=True)
    shutil.copytree(ROOT/'evidence',DEST/'data')
    shutil.copytree(ROOT/'review-independent',DEST/'validation/results')
    for name in ['source.tar.gz','source-hashes.json','evidence.tar.gz','build.log','build.sh','python-tests.log','standalone-tests.log','aligned-native-local.json','collect.log','collect.sh','launch.sh']:
        shutil.copyfile(ROOT/name,DEST/'provenance'/name)
    shutil.copyfile(ROOT/'verify77.py',DEST/'validation/verify77.py')
    shutil.copyfile(Path(__file__),DEST/'validation/archive77.py')
    entries={}
    for label,source in [('object-prior',ROOT.parent/'hotspot-disk-demand75/object-prior-model'),('capacity-boundary',ROOT/'capacity-boundary')]:
        target=DEST/'models'/label;target.mkdir()
        copied=[];excluded=[]
        for p in sorted(source.rglob('*')):
            if not p.is_file():continue
            relative=p.relative_to(source)
            if p.suffix not in ['.py','.cpp','.h','.json','.txt','.md'] or '__pycache__' in p.parts:
                excluded.append(str(relative));continue
            output=target/relative;output.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,output);output.chmod(0o644);copied.append(str(relative))
        entries[label]=dict(files=copied,excluded=excluded,hashes=hashes(target),speed_evidence=False)
    dump(DEST/'provenance/model-files.json',entries)
    for name in ['tail-trace.py','tail-trace-analysis.py','tail-trace-freeze.json','tail-trace-selftest.json','tail-trace-README.md']:
        shutil.copyfile(ROOT/name,DEST/'diagnostics/tail-trace/tools'/name)
    dump(DEST/'diagnostics/tail-trace/status.json',dict(diagnosis_only=True,performance_evidence=False,status='awaiting_separately_collected_trace_evidence',primary_matrix_unchanged=True))
    raw=hashes(DEST/'data');assert raw==hashes(ROOT/'evidence') and len(raw)==290
    with tarfile.open(ROOT/'evidence.tar.gz') as archive:
        stored={m.name:hashlib.sha256(archive.extractfile(m).read()).hexdigest() for m in archive.getmembers() if m.isfile()}
    assert stored==raw
    dump(DEST/'provenance/data-hashes.json',raw)
    dump(DEST/'provenance/archive-hashes.json',dict(archives={name:dict(bytes=(ROOT/name).stat().st_size,sha256=sha(ROOT/name)) for name in ['source.tar.gz','evidence.tar.gz']},binary_sha256='6334375577555abe6886db40a49f55f379f8291993880fdf6f8d5c4cdd2cf8cb',binary_entity_archived=False))
    assert hashes(ROOT/'review')==hashes(ROOT/'review-independent')
    dump(DEST/'validation/independent-review.json',dict(passed=True,independently_reexecuted=True,outputs_match_original_review=hashes(ROOT/'review-independent'),server_access=False,strict_primary_passed=12,strict_primary_total=16,all_primary_passed=False))
    print(DEST)

if __name__=='__main__':main()
