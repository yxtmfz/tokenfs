#!/usr/bin/env python3
"""Read frozen local 77 data only; descriptive diagnosis, never acceptance reruns."""
from pathlib import Path
import json,math,statistics,collections,hashlib
BASE=Path(__file__).resolve().parents[2]/'hotspot-object77'
OUT=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
q=lambda xs,p:sorted(xs)[max(0,math.ceil(p*len(xs))-1)]
summary=[]
for case in sorted((BASE/'evidence/development').glob('*/*/result.json')):
 r=read(case);m=r['metrics'];req=read(case.with_name('requests.json'));seen=set();first=[];reuse=[];classes={}
 for a in req:
  cls='first' if a['key'] not in seen else 'reused';classes[a['index']]=cls;seen.add(a['key'])
  (first if cls=='first' else reuse).append(a['response_seconds']*1000)
 sorted_req=sorted(req,key=lambda x:x['response_seconds'],reverse=True)
 top=sorted_req[:math.ceil(.01*len(req))]
 summary.append(dict(block=case.parent.parent.name,arm=case.parent.name,wall_s=r['job_wall_s'],throughput=r['effective_mib_s'],p99_ms=r['request_p99_s']*1000,
  p99_neighbor_11th_12th_13th_ms=[a['response_seconds']*1000 for a in sorted_req[10:13]],first_count=len(first),reused_count=len(reuse),tail_first=sum(classes[a['index']]=='first' for a in top),
  first_mean_ms=statistics.mean(first),reused_mean_ms=statistics.mean(reuse),first_p99_ms=q(first,.99),reused_p99_ms=q(reuse,.99),
  tiers={t:m.get(t+'_read_open_count',0) for t in ['remote','local','inflight']},copies=m.get('promote_count',0)+m.get('cross_gpu_replica_create_count',0),
  submitted=m.get('background_submitted',0),no_gain=m.get('shared_placement_no_gain',0),selected=m.get('shared_placement_selected',0),
  read_measured_s=m.get('read_latency_us_total',0)/1e6,capture_s=m.get('read_fill_capture_us',0)/1e6,daemon_cpu_s=r['daemon_cpu_s'],drain_s=r['drain_s'],
  profile_enabled=read(case.with_name('config.json'))['policy']['profile_control_path']))
by={(x['block'],x['arm']):x for x in summary};pairs=[]
for b in sorted({x['block'] for x in summary}):
 f=by[b,'Full'];n=by[b,'NoHotspot']
 pairs.append(dict(block=b,saved_remote_reads=n['tiers']['remote']-f['tiers']['remote'],saved_local_reads=n['tiers']['local']-f['tiers']['local'],ram_difference=f['tiers']['inflight']-n['tiers']['inflight'],additional_copies=f['copies']-n['copies'],saved_submissions=n['submitted']-f['submitted'],gain_pct=(n['wall_s']/f['wall_s']-1)*100,p99_reduction_pct=(1-f['p99_ms']/n['p99_ms'])*100,first_mean_delta_ms=f['first_mean_ms']-n['first_mean_ms'],reused_mean_delta_ms=f['reused_mean_ms']-n['reused_mean_ms']))
trace=[]
for arm in ['Full','NoHotspot']:
 d=BASE/'tail-evidence'/arm;events=read(d/'request-trace.json')['events'];r=read(d/'result.json');analysis=read(BASE/'tail-review/analysis.json')[arm]
 plans=[e for e in events if e['op']=='shared_plan'];reads=[e for e in events if e['op']=='read'];releases=[e for e in events if e['op']=='release'];copies=[e for e in events if e['op']=='copy_pipeline']
 duration=lambda es:sum(e['end_ns']-e['start_ns'] for e in es)/1e9
 groups={}
 for tier in ['selected','rejected']:
  es=[e for e in plans if e['tier']==tier];groups[tier]=dict(count=len(es),sum_s=duration(es),max_ms=max((e['end_ns']-e['start_ns'] for e in es),default=0)/1e6)
 trace.append(dict(arm=arm,profile_plan_measured_s=r['metrics']['shared_plan_latency_us_total']/1e6,plans=groups,all_plan_s=duration(plans),
   trace_read_s=duration(reads),counter_read_s=r['metrics']['read_latency_us_total']/1e6,read_after_counter_s=duration(reads)-r['metrics']['read_latency_us_total']/1e6,
   read_pread_s=sum(e['pread_ns'] for e in reads)/1e9,release_s=duration(releases),release_flush_s=sum(e['flush_ns'] for e in releases)/1e9,
   release_overlap_client_s=analysis['groups']['all']['means']['release_inside_client_ms']*1152/1000,
   same_tier_last_data_non_pread_ms={x['access_class']+'/'+x['tier']:x['means']['last_data_non_pread_ms'] for x in analysis['strata'] if x['n']},
   first_requests=analysis['groups']['first']['n'],first_pread_mean_ms=analysis['groups']['first']['means']['pread_ms'],
   tail_first=sum(x['access_class']=='first' for x in analysis['top12']),tail_remote=sum(x['tier']=='remote' for x in analysis['top12']),
   capture_s=r['metrics']['read_fill_capture_us']/1e6,copy_pipeline_s=duration(copies)))
result=dict(diagnosis_only=True,performance_acceptance=False,source='frozen77 local files; no server/new run',speed_runs=summary,h_pairs=pairs,trace_diagnostics=trace)
(OUT/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'h_pairs':pairs,'trace_diagnostics':trace},indent=2))
