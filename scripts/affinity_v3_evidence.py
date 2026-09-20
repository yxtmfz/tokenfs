#!/usr/bin/env python3
"""Offline evidence audit for the held-out affinity-only revision."""
from __future__ import annotations
import argparse,hashlib,json,math,shutil,tempfile,statistics
from pathlib import Path
import affinity_v3_study as study
from measured_study import digest

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(condition,message):
    if not condition:raise ValueError(message)

def verify(data,source):
    study.activate();repo=Path(__file__).resolve().parents[1]
    freeze_path=repo/'study-configs/affinity-v3-freeze-01.json';f=read(freeze_path)
    main=data/'cn7/affinity-v3-confirmation-01';m=read(main/'manifest.json');context=read(data/'cn7/confirmation-launch-context.json')
    require(context['freeze']==f and context['freeze_sha256']==sha(freeze_path),'launch freeze changed')
    require(m['source_hashes']==f['source_hashes'] and m['binary_sha256']==f['binary_sha256'],'runtime changed')
    require({n:sha(repo/n) for n in study.SOURCES}==f['source_hashes'],'checkout differs from frozen runtime')
    spec_path=repo/'study-configs/affinity-v3-confirmation-01.json'
    require(sha(spec_path)==f['spec_sha256'] and m['spec']==read(spec_path),'spec changed')
    require(m['nvme_identity']['transport']=='tcp' and m['nvme_identity']['subsysnqn']=='nqn.2026-09.local.aura-kv:remote-cn7'
            and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(','),'remote identity changed')
    batches=[]
    for host,names in [('cn7',[('correctness',24),('development',48),('confirmation',288)]),('cn8',[('correctness',24)])]:
        final=read(data/host/'final-context.json')
        require(final['binary_sha256']==f['binary_sha256'] and final['source_hashes']==f['source_hashes'],'final artifact changed')
        require(not final['remaining_mounts'],'active test mount remained')
        for short,count in names:
            name='affinity-v3-'+short+'-01';require((data/host/(name+'.exit')).read_text().strip()=='0','batch failed')
            a=study.core.audit(data/host/name);require(a['passed'] and a['expected_runs']==a['checked_runs']==count,'invalid/incomplete '+name)
            batches.append(dict(host=host,batch=name,cases=count,passed=True))
    wp=repo/'study-configs/affinity-v3-public-windows.json';windows=read(wp)
    require(sha(wp)==f['public_window_manifest_sha256'] and sha(source)==windows['source_sha256'],'public source/window changed')
    raw=[json.loads(x) for x in source.read_text().splitlines()];cut=len(raw)//5
    old=read(repo/'study-configs/measured-b3-freeze.json');old3=read(repo/'study-configs/affinity-joint-public-windows.json')
    old4=read(repo/'study-configs/affinity-v2-public-windows.json')
    occupied=[(w['first_source_request'],w['last_source_request']) for w in old['public_windows'] if w['source']=='toolagent_trace.jsonl']+[(w['first'],w['last']) for w in old3['windows']]+[(w['first'],w['last']) for w in old4['windows']]
    checked=0
    for b in m['spec']['blocks']:
        if b['scenario']!='public_toolagent':continue
        origin=b['public_origin'];start=cut+origin['source_request_offset'];first=raw[start]['timestamp'];events=[];keys={}
        require(origin['split']=='confirmation' and origin['sha256']==windows['source_sha256'],'invalid public origin')
        for index,row in enumerate(raw[start:],start=start):
            for block_hash in row['hash_ids']:
                key=keys.setdefault(str(block_hash),len(keys));events.append(dict(index=len(events),key=key,caller=index%3,bytes=b['shard_mib']*1048576,source_request=index,source_hash=str(block_hash),source_arrival_ms=row['timestamp']-first))
                if len(events)==b['requests']:break
            if len(events)==b['requests']:break
        end=events[-1]['source_request'];w=next(w for w in windows['windows'] if w['seed']==b['seed'])
        require(events==b['events']==read(main/b['id']/'trace.json'),'public replay differs')
        require(start>=cut and all(end<a or start>z for a,z in occupied),'public windows overlap')
        require((start,end)==(w['first'],w['last']) and digest(events)==w['trace_sha256'],'public manifest differs')
        occupied.append((start,end));checked+=1
    require(checked==12,'wrong window count')
    saved={n:(main/(n+'.json')).read_text() for n in ['summary','comparisons']};original={n:json.loads(v) for n,v in saved.items()}
    try:
        study.report(main);reproduced={n:read(main/(n+'.json')) for n in saved}
    finally:
        for n,v in saved.items():(main/(n+'.json')).write_text(v)
    require(original['summary']==reproduced['summary'],'summary differs');rounding=[]
    require(len(original['comparisons'])==len(reproduced['comparisons'])==16,'comparison matrix incomplete')
    for index,(a,b) in enumerate(zip(original['comparisons'],reproduced['comparisons'])):
        require(a.keys()==b.keys(),'comparison fields differ')
        for field,value in a.items():
            if value==b[field]:continue
            require(field in ['time_ratio','throughput_change_pct','with_drain_ratio'] and isinstance(value,float) and isinstance(b[field],float) and math.isfinite(value) and math.isfinite(b[field]) and abs(value-b[field])<=1e-12,'statistical reproduction differs: '+field)
            rounding.append(dict(row=index,field=field,server=value,local=b[field],absolute_difference=abs(value-b[field])))
        logs=[]
        for block in m['spec']['blocks']:
            if block['scenario']!=a['scenario']:continue
            treatment=read(main/block['id']/'P-new/result.json');baseline=read(main/block['id']/a['baseline']/'result.json')
            logs.append(math.log(treatment['job_wall_s']/baseline['job_wall_s']))
        require(len(logs)==12 and abs(math.exp(sum(logs)/12)-a['time_ratio'])<=1e-12,'independent paired ratio differs')
    for block in m['spec']['blocks']:
        for variant in study.VARIANTS:
            r=read(main/block['id']/variant/'result.json');metrics=r['metrics']
            adjusted=metrics.get('measured_affinity_reweighted_plans',0)
            require(isinstance(adjusted,int) and adjusted>=0,'invalid mechanism accounting')
            if variant!='P-new':require(adjusted==0 and metrics.get('measured_affinity_context_resets',0)==0,'new mechanism leaked into comparator')
            if variant=='P-new':require(metrics.get('measured_precheck_affinity',0)+metrics.get('measured_commit_affinity',0)==0,'legacy veto active in new mode')
    negatives=[]
    with tempfile.TemporaryDirectory(prefix='affinity-v3-negative-') as d:
        scratch=Path(d);block=m['spec']['blocks'][0];shutil.copytree(main/block['id'],scratch/block['id'])
        fixture=json.loads(json.dumps(m));fixture['spec']['blocks']=[block];fixture['spec_sha256']=digest(fixture['spec']);(scratch/'manifest.json').write_text(json.dumps(fixture))
        require(study.core.audit(scratch)['passed'],'invalid negative fixture');case=scratch/block['id']/'P-new'
        for kind in ['bytes','configuration','timeline']:
            path=case/('config.json' if kind=='configuration' else 'requests.json' if kind=='timeline' else 'result.json');text=path.read_text();value=json.loads(text)
            if kind=='bytes':value['logical_bytes']-=1
            elif kind=='configuration':value['policy']['measured_affinity_gate']=False
            else:value[0]['issued_s']=-1
            path.write_text(json.dumps(value));rejected=not study.core.audit(scratch)['passed'];path.write_text(text)
            require(rejected,'tampering accepted');negatives.append(dict(kind=kind,rejected=True))
        require(study.core.audit(scratch)['passed'],'negative fixture restoration failed')
    return dict(passed=True,performance_runs=288,content_cases=48,development_runs=48,batches=batches,public_windows=checked,independent_comparisons=16,rounding_differences=rounding,negative_checks=negatives,binary_sha256=f['binary_sha256'],algorithm_revision=f['algorithm_revision'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--public-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();r=verify(a.data_root,a.public_source);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r))
