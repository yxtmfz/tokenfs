#!/usr/bin/env python3
"""Prepare batch80 archive only after actual raw evidence and two reviews exist.

Without --execute this lists missing prerequisites and creates no report/data.
It never starts a benchmark, synthesizes raw results, or contacts a server.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,tarfile

ROOT=Path(__file__).resolve().parent
WORK=ROOT.parent
OUT=WORK/'tokenfs-eval/reports/latest/paper-experiments/80_indexed_precheck_development'
SHA_SOURCE='f6691da87b5cf91edc594cad618562f77f0de5fb8a6060fb395f69fc64bfbd45'
SHA_BINARY='f5e2981b8b4f0ce54bb2994e53998608de4cec4a3c861531e8e86e0aab031f71'
PROVENANCE=['source.tar.gz','source-hashes.json','evidence.tar.gz','build.log','build.sh','python-tests.log','standalone-tests.log','package.py','launch.sh','collect.sh','collect.log','ci-receipt.json']
VALIDATION=['verify80.py','preaudit80.py','preaudit-review.json','preaudit-targeted-tests.log','preaudit-final.log']
TEXT_EXTENSIONS={'.cpp','.h','.py','.json','.txt','.tsv','.md','.log'}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text())
def dump(p,value):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def copy(src,dst):dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
def hashes(folder):return {str(p.relative_to(folder)):sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}
def unpack(archive,parent,expected_root):
    seen=set()
    with tarfile.open(archive) as handle:
        for member in handle.getmembers():
            name=Path(member.name)
            assert member.isfile() and not name.is_absolute() and '..' not in name.parts and name.parts[0]==expected_root
            assert member.name not in seen;seen.add(member.name)
            destination=parent/member.name;destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(handle.extractfile(member).read())

def main(execute=False):
    prerequisites=[ROOT/name for name in PROVENANCE+VALIDATION]+[
        ROOT/'evidence/provenance/freeze.json',ROOT/'review-independent/review.json',ROOT/'root-review/review.json',
        ROOT/'index-independent-review.md',ROOT/'verify-archive80.py',ROOT/'analyze-mechanisms80.py',ROOT/'refresh-manifest80.py',
        WORK/'hotspot-index80/local-validation/source-hashes.json',
        WORK/'hotspot-index80-independent-review/final-source-identity.json',
        WORK/'hotspot-next-review/tail79-readonly/manifest.json',
        WORK/'hotspot-run-unit-review-source.tar.gz',WORK/'hotspot-run-unit-review-source-manifest.json']
    missing=[str(p) for p in prerequisites if not p.is_file()]
    if not execute:
        print(json.dumps(dict(archive_not_created=True,missing_prerequisites=missing,ready_for_archive=not missing)))
        return
    assert not missing,missing
    assert not OUT.exists(),'Report already exists: inspect before changing archive.'
    review=load(ROOT/'review-independent/review.json')
    assert review['passed'] and review['speed_runs']==24 and review['content_checks']==576 and review['source_files']==355
    assert review['source_archive_sha256']==sha(ROOT/'source.tar.gz')==SHA_SOURCE
    assert review['binary_sha256']==SHA_BINARY
    assert review['raw_evidence_unchanged']
    agreement={p.name:dict(independent_sha256=sha(p),root_sha256=sha(ROOT/'root-review'/p.name)) for p in (ROOT/'review-independent').iterdir() if p.is_file()}
    assert len(agreement)==8 and all(x['independent_sha256']==x['root_sha256'] for x in agreement.values())
    raw=hashes(ROOT/'evidence');assert raw==load(ROOT/'review-independent/evidence-hashes.json')
    # Only actual complete raw receipts and verified derived outputs enter data.
    shutil.copytree(ROOT/'evidence',OUT/'data')
    shutil.copytree(ROOT/'review-independent',OUT/'validation/results')
    for name in PROVENANCE:copy(ROOT/name,OUT/'provenance'/name)
    for name in VALIDATION:copy(ROOT/name,OUT/'validation'/name)
    copy(ROOT/'verify-archive80.py',OUT/'validation/verify-archive.py')
    copy(ROOT/'analyze-mechanisms80.py',OUT/'validation/analyze-mechanisms.py')
    copy(ROOT/'refresh-manifest80.py',OUT/'validation/refresh-manifest.py')
    copy(Path(__file__),OUT/'provenance/prepare-archive80.py')
    dump(OUT/'provenance/data-hashes.json',raw)
    dump(OUT/'provenance/archive-hashes.json',dict(archives={name:dict(bytes=(ROOT/name).stat().st_size,sha256=sha(ROOT/name)) for name in ['source.tar.gz','evidence.tar.gz']}))
    dump(OUT/'validation/independent-review-agreement.json',dict(passed=True,outputs=agreement,byte_identical=True))
    ancillary={}
    for name,folder in [('local-harness',WORK/'hotspot-index80/local-validation'),
                        ('index-independent-review',WORK/'hotspot-index80-independent-review'),
                        ('tail79-readonly',WORK/'hotspot-next-review/tail79-readonly')]:
        included={};excluded=[]
        for source in sorted(folder.rglob('*')):
            if not source.is_file():continue
            relative=source.relative_to(folder)
            if source.suffix in TEXT_EXTENSIONS and not any(x.endswith('.dSYM') for x in relative.parts):
                copy(source,OUT/'diagnostics'/name/relative);included[str(relative)]=sha(source)
            else:excluded.append(str(relative))
        ancillary[name]=dict(hashes=included,excluded=excluded)
    copy(ROOT/'index-independent-review.md',OUT/'diagnostics/index-independent-review/README.md')
    ancillary['index-independent-review']['hashes']['README.md']=sha(ROOT/'index-independent-review.md')
    model='hotspot-run-unit-review';archive=WORK/(model+'-source.tar.gz');receipt=WORK/(model+'-source-manifest.json');manifest=load(receipt)
    assert sha(archive)==manifest['archive_sha256'] and manifest['file_count']==158
    for source in [archive,receipt]:copy(source,OUT/'provenance'/source.name)
    unpack(archive,OUT/'models',model)
    model_hashes={model+'/'+p:h for p,h in hashes(OUT/'models'/model).items()}
    assert model_hashes=={item['path']:item['sha256'] for item in manifest['members']}
    ancillary[model]=dict(hashes=model_hashes,archive_sha256=sha(archive),files=158)
    dump(OUT/'provenance/ancillary-files.json',ancillary)
    assert hashes(OUT/'data')==raw
    print(json.dumps(dict(archive=str(OUT),raw_files=len(raw),derived_from_real_reviews_only=True,
        primary_passed=review['full_acceptance_primary'],primary_total=16,
        index_implementation_passed=review['full_acceptance_indexed_precheck'],index_total=4,
        remaining='Write reviewed README; run analyze-mechanisms, refresh-manifest, verify-archive.')))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--execute',action='store_true')
    main(parser.parse_args().execute)
