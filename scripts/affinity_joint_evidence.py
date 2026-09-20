#!/usr/bin/env python3
"""Offline round-3 source, public-window and statistics reproduction audit."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import tempfile

from affinity_joint_study import audit, report, SOURCES
from measured_study import digest


def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(value,message):
    if not value:raise ValueError(message)


def verify(data,source):
    repo=Path(__file__).resolve().parents[1]
    freeze_path=repo/'study-configs/affinity-joint-freeze-01.json';f=read(freeze_path)
    c7=data/'cn7';c8=data/'cn8';root=c7/'confirmation-01';m=read(root/'manifest.json')
    context=read(c7/'confirmation-launch-context.json')
    require(context['freeze_sha256']==sha(freeze_path) and context['freeze']==f,'launch freeze changed')
    require(m['source_hashes']==f['source_hashes'] and m['binary_sha256']==f['binary_sha256'],'runtime identity changed')
    require(all(sha(repo/p)==f['source_hashes'][p] for p in SOURCES),'checkout differs from runtime freeze')
    spec_path=repo/'study-configs/affinity-joint-confirmation-01.json'
    require(sha(spec_path)==f['spec_sha256'] and m['spec']==read(spec_path),'spec changed')
    require(m['nvme_identity']['transport']=='tcp' and m['nvme_identity']['subsysnqn']=='nqn.2026-09.local.aura-kv:remote-cn7'
            and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(','),'remote identity changed')
    batches=[]
    for host,names in [('cn7',[('correctness-01',54),('correctness-02',12),('development-01',54),('development-02',18),('confirmation-01',576)]),
                       ('cn8',[('correctness-01',54),('correctness-02',12)])]:
        final=read(data/host/'final-runtime-context.json')
        require(final['binary_sha256']==f['binary_sha256'] and final['runtime_hashes']==f['source_hashes'],'end-of-study source drift')
        require(not final['remaining_test_mounts'],'test mount remained active')
        for name,count in names:
            require((data/host/(name+'.exit')).read_text().strip()=='0','nonzero batch exit')
            a=audit(data/host/name)
            require(a['passed'] and a['checked_runs']==a['expected_runs']==count,'incomplete/invalid batch '+host+'/'+name)
            batches.append(dict(host=host,batch=name,checked=count,passed=True))

    windows_path=repo/'study-configs/affinity-joint-public-windows.json';windows=read(windows_path)
    require(sha(windows_path)==f['public_window_manifest_sha256'],'window manifest changed')
    require(sha(source)==windows['source_sha256'],'public source changed')
    raw=[json.loads(line) for line in source.read_text().splitlines()];cut=len(raw)//5
    old=read(repo/'study-configs/measured-b3-freeze.json')
    occupied=[(w['first_source_request'],w['last_source_request']) for w in old['public_windows'] if w['source']=='toolagent_trace.jsonl']
    checked_public=0
    for b in m['spec']['blocks']:
        if b['scenario']!='public_toolagent':continue
        origin=b['public_origin'];start=cut+origin['source_request_offset'];keys={};events=[];first=raw[start]['timestamp']
        require(origin['sha256']==windows['source_sha256'] and origin['split']=='confirmation','public origin changed')
        for index,row in enumerate(raw[start:],start=start):
            for block_hash in row['hash_ids']:
                key=keys.setdefault(str(block_hash),len(keys))
                events.append(dict(index=len(events),key=key,caller=index%3,bytes=b['shard_mib']*1048576,
                    source_request=index,source_hash=str(block_hash),source_arrival_ms=row['timestamp']-first))
                if len(events)==b['requests']:break
            if len(events)==b['requests']:break
        require(events==b['events']==read(root/b['id']/'trace.json'),'public replay changed')
        end=events[-1]['source_request']
        require(start>=cut and all(end<a or start>z for a,z in occupied),'overlapping public window')
        occupied.append((start,end))
        w=next(w for w in windows['windows'] if w['seed']==b['seed'])
        require((start,end)==(w['first'],w['last']) and digest(events)==w['trace_sha256'],'frozen window differs')
        checked_public+=1
    require(checked_public==12,'public window count')

    saved={name:(root/(name+'.json')).read_text() for name in ['summary','comparisons','interactions','activity']}
    originals={name:json.loads(value) for name,value in saved.items()}
    try:
        report(root)
        reproduced={name:read(root/(name+'.json')) for name in saved}
    finally:
        for name,value in saved.items():(root/(name+'.json')).write_text(value)
    for name in ['summary','interactions']:
        require(reproduced[name]==originals[name],'server/local statistic mismatch: '+name)
    rounding=[]
    require(len(reproduced['comparisons'])==len(originals['comparisons']),'comparison count changed')
    for index,(a,b) in enumerate(zip(originals['comparisons'],reproduced['comparisons'])):
        require(a.keys()==b.keys(),'comparison fields changed')
        for field,value in a.items():
            if value==b[field]:continue
            require(field in ['time_ratio','throughput_change_pct','with_drain_ratio']
                    and isinstance(value,float) and isinstance(b[field],float)
                    and math.isfinite(value) and math.isfinite(b[field])
                    and abs(value-b[field])<=1e-12,'server/local comparison mismatch: '+field)
            rounding.append(dict(row=index,scenario=a['scenario'],baseline=a['baseline'],field=field,
                server=value,local=b[field],absolute_difference=abs(value-b[field])))
    key=lambda r:(r['block'],r['strategy'])
    require(sorted(reproduced['activity'],key=key)==sorted(originals['activity'],key=key),'mechanism records mismatch')
    for row in originals['comparisons']:
        logs=[]
        for b in m['spec']['blocks']:
            if b['scenario']!=row['scenario']:continue
            a=read(root/b['id']/row['treatment']/'result.json');other=read(root/b['id']/row['baseline']/'result.json')
            logs.append(math.log(a['job_wall_s']/other['job_wall_s']))
        require(len(logs)==12 and math.isclose(math.exp(sum(logs)/12),row['time_ratio'],rel_tol=1e-12),'independent ratio mismatch')
    require(len(originals['comparisons'])==42,'comparison matrix incomplete')

    # Negative checks use one copied block and never modify any original evidence.
    negatives=[]
    with tempfile.TemporaryDirectory(prefix='tokenfs-aj-audit-') as d:
        scratch=Path(d);block=m['spec']['blocks'][0];shutil.copytree(root/block['id'],scratch/block['id'])
        fixture=json.loads(json.dumps(m));fixture['spec']['blocks']=[block];fixture['spec_sha256']=digest(fixture['spec'])
        (scratch/'manifest.json').write_text(json.dumps(fixture))
        require(audit(scratch)['passed'],'negative-check fixture invalid')
        case=scratch/block['id']/block['variants'][0]
        for kind in ['bytes','configuration','timeline']:
            path=case/('config.json' if kind=='configuration' else 'requests.json' if kind=='timeline' else 'result.json')
            saved=path.read_text();value=json.loads(saved)
            if kind=='bytes':value['logical_bytes']-=1
            elif kind=='configuration':value['policy']['private_cache_domains']=False
            else:value[0]['issued_s']=-1
            path.write_text(json.dumps(value));rejected=not audit(scratch)['passed'];path.write_text(saved)
            require(rejected,'tampering accepted: '+kind);negatives.append(dict(case=kind,rejected=True))
        require(audit(scratch)['passed'],'negative fixture did not restore')
    return dict(passed=True,batches=batches,performance_cases=576,content_cases=132,development_cases=72,
        frozen_public_windows=checked_public,exact_statistics_json=['summary.json','interactions.json'],
        comparisons_equal_within_absolute_1e_12=True,comparison_rounding_differences=rounding,
        mechanism_records_equal_after_canonical_order=True,independent_paired_ratios=42,
        negative_checks=negatives,algorithm_revision=f['algorithm_revision'],binary_sha256=f['binary_sha256'])


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--public-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();result=verify(args.data_root,args.public_source)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result))
