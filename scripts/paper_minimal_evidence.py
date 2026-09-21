#!/usr/bin/env python3
"""Independent offline replay of the scoped H/J evidence, with tamper checks."""
from __future__ import annotations
import argparse,hashlib,json,math,random,shutil,statistics,tempfile
from pathlib import Path
import paper_minimal_study as study
from measured_study import digest,application

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,message):
    if not v:raise ValueError(message)

def verify(data,public_source):
    study.activate();repo=Path(__file__).resolve().parents[1]
    fp=repo/'study-configs/paper-minimal-freeze-01.json';f=read(fp)
    require({p:sha(repo/p) for p in study.SOURCES}==f['source_hashes'],'runtime source differs')
    require(sha(repo/'docs/paper-minimal-plan.md')==f['plan_sha256'],'plan differs')
    require(sha(repo/'study-configs/paper-minimal-confirmation-01.json')==f['spec_sha256'],'formal spec differs')
    require(sha(repo/'study-configs/paper-minimal-sensitivity-01.json')==f['sensitivity_spec_sha256'],'sensitivity spec differs')
    context=read(data/'cn7/confirmation-launch-context.json')
    require(context['freeze']==f and context['freeze_sha256']==sha(fp),'launch freeze differs')
    batches=[]
    for host,names in [('cn7',[('correctness',28),('development',28),('confirmation',336),('sensitivity',12)]),('cn8',[('correctness',28)])]:
        final=read(data/host/'final-context.json')
        require(final['binary_sha256']==f['binary_sha256'] and final['source_hashes']==f['source_hashes'],'final runtime differs')
        require(not final['remaining_mounts'],'test mounts remain')
        for label,count in names:
            name='paper-minimal-'+label+'-01';root=data/host/name;m=read(root/'manifest.json')
            require(m['verify']==(label=='correctness') and m['backend_direct'] is True,'wrong verification or I/O mode')
            require((data/host/(name+'.exit')).read_text().strip()=='0','failed batch '+name)
            require(m['binary_sha256']==f['binary_sha256'] and m['source_hashes']==f['source_hashes'],'batch runtime differs')
            require(m['spec']==read(repo/'study-configs'/(name+'.json')),'batch spec differs')
            a=study.core.audit(root);require(a['passed'] and a['checked_runs']==a['expected_runs']==count,'batch audit '+name)
            for block in m['spec']['blocks']:
                events=study.core.trace(block);expected=read(root/block['id']/'objects.json')
                for key in {e['key'] for e in events}:
                    payload=random.Random(block['seed']*100000+key).randbytes(1048576)
                    require(hashlib.sha256(payload*block['shard_mib']).hexdigest()==expected[str(key)],'payload provenance differs')
                for variant in block['variants']:
                    r=read(root/block['id']/variant/'result.json');mm=r['metrics']
                    require(not any(mm.get(k,0) for k in ['measured_affinity_context_resets','measured_affinity_reweighted_plans','measured_precheck_affinity','measured_commit_affinity']),'affinity unexpectedly active')
                    if variant not in ['Full','no-J']:require(mm.get('measured_shift_resets',0)==0,'hot reset leaked into baseline')
            batches.append(dict(host=host,batch=name,checked=count,passed=True))
    main=data/'cn7/paper-minimal-confirmation-01';m=read(main/'manifest.json')
    require(m['nvme_identity']['transport']=='tcp' and m['nvme_identity']['subsysnqn']=='nqn.2026-09.local.aura-kv:remote-cn7' and 'traddr=28.10.10.13' in m['nvme_identity']['address'].split(','),'wrong storage target')
    wp=repo/'study-configs/paper-minimal-public-windows.json';wm=read(wp)
    require(sha(wp)==f['public_window_manifest_sha256'] and sha(public_source)==wm['source_sha256'],'public manifest/source differs')
    old=read(repo/'study-configs/measured-b3-freeze.json')
    used=[(w['first_source_request'],w['last_source_request']) for w in old['public_windows'] if w['source']=='toolagent_trace.jsonl']
    for n in ['affinity-joint','affinity-v2','affinity-v3']:
        used += [(w['first'],w['last']) for w in read(repo/f'study-configs/{n}-public-windows.json')['windows']]
    checked=0
    for b in m['spec']['blocks']:
        if b['scenario']!='public_toolagent':continue
        o=b['public_origin'];_,events,origin=application(public_source,'confirmation',o['source_request_offset'],b['requests'],b['shard_mib'])
        for e in events:e['caller']=e['source_request']%3
        require(o==origin and events==b['events']==read(main/b['id']/'trace.json'),'public trace differs')
        first,last=events[0]['source_request'],events[-1]['source_request']
        require(all(last<a or first>z for a,z in used),'public overlap')
        window=next(w for w in wm['windows'] if w['seed']==b['seed'])
        require((first,last)==(window['first'],window['last']) and digest(events)==window['trace_sha256'],'window mismatch')
        used.append((first,last));checked+=1
    require(checked==12,'public window count')
    rounding=[];comparisons_count=0
    for label in ['development','confirmation','sensitivity']:
        root=data/('cn7/paper-minimal-'+label+'-01')
        saved={n:(root/(n+'.json')).read_text() for n in ['summary','comparisons','interactions']}
        try:
            study.report(root);rerun={n:read(root/(n+'.json')) for n in saved}
        finally:
            for n,v in saved.items():(root/(n+'.json')).write_text(v)
        def compare(a,b,path):
            if isinstance(a,dict):
                require(isinstance(b,dict) and a.keys()==b.keys(),'fields differ '+path)
                for k in a:compare(a[k],b[k],path+'/'+k)
            elif isinstance(a,list):
                require(isinstance(b,list) and len(a)==len(b),'length differs '+path)
                for i,(x,y) in enumerate(zip(a,b)):compare(x,y,path+'/'+str(i))
            elif a!=b:
                allowed=isinstance(a,float) and isinstance(b,float) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<=1e-12 and not any(k in path for k in ['p_raw','p_holm','verdict'])
                require(allowed,'reproduction differs '+path)
                rounding.append(dict(path=path,server=a,local=b,absolute_difference=abs(a-b)))
        for name,value in saved.items():compare(json.loads(value),rerun[name],label+'/'+name)
        if label=='confirmation':
            require(len(rerun['comparisons'])==23,'comparison count changed')
            for c in rerun['comparisons']:
                logs=[]
                for b in m['spec']['blocks']:
                    if b['scenario']==c['scenario'] and {c['treatment'],c['baseline']}<=set(b['variants']):
                        x=read(main/b['id']/c['treatment']/'result.json');y=read(main/b['id']/c['baseline']/'result.json')
                        logs.append(math.log(x['job_wall_s']/y['job_wall_s']))
                require(len(logs)==12 and abs(math.exp(sum(logs)/12)-c['time_ratio'])<1e-12,'independent ratio differs')
            comparisons_count=len(rerun['comparisons'])
    negatives=[]
    with tempfile.TemporaryDirectory(prefix='minimal-negative-') as tmp:
        scratch=Path(tmp);b=m['spec']['blocks'][0];shutil.copytree(main/b['id'],scratch/b['id'])
        fixture=json.loads(json.dumps(m));fixture['spec']['blocks']=[b];fixture['spec_sha256']=digest(fixture['spec'])
        (scratch/'manifest.json').write_text(json.dumps(fixture));require(study.core.audit(scratch)['passed'],'invalid negative fixture')
        for kind,file in [('bytes','result.json'),('configuration','config.json'),('timeline','requests.json')]:
            p=scratch/b['id']/'Full'/file;original=p.read_text();v=json.loads(original)
            if kind=='bytes':v['logical_bytes']-=1
            elif kind=='configuration':v['policy']['measured_affinity_gate']=True
            else:v[0]['issued_s']=-1
            p.write_text(json.dumps(v));rejected=not study.core.audit(scratch)['passed'];p.write_text(original)
            require(rejected,'tampering accepted');negatives.append(dict(kind=kind,rejected=True))
        require(study.core.audit(scratch)['passed'],'fixture restore failed')
    return dict(passed=True,performance_runs=336,content_cases=56,development_runs=28,sensitivity_runs=12,
                batches=batches,public_windows=checked,independent_comparisons=comparisons_count,
                rounding_differences=rounding,negative_checks=negatives,algorithm_revision=f['algorithm_revision'],binary_sha256=f['binary_sha256'])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--public-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();r=verify(a.data_root,a.public_source);a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r))
