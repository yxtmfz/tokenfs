"""Post-hoc descriptive phase accounting; no added samples or hypothesis tests."""
from pathlib import Path
import argparse,json,statistics

def analyze(main):
 read=lambda p:json.loads(p.read_text())
 m=read(main/'manifest.json');records=[]
 for b in m['spec']['blocks']:
  if b['scenario']!='hot_shift':continue
  trace=read(main/b['id']/'trace.json');n=len(trace)
  assert n%4==0
  for name in b['variants']:
   case=main/b['id']/name;r=read(case/'result.json');rows=read(case/'requests.json')
   assert len(rows)==n
   prior=0;bytes_sum=0;seconds_sum=0
   for phase in range(4):
    start=phase*n//4;end=(phase+1)*n//4
    until=rows[end-1]['completed_s'] if phase<3 else r['job_wall_s']
    elapsed=until-prior;logical=sum(e['bytes'] for e in trace[start:end]);assert elapsed>0
    records.append(dict(block=b['id'],strategy=name,phase=phase+1,logical_bytes=logical,elapsed_s=elapsed,mib_s=logical/1048576/elapsed))
    prior=until;bytes_sum+=logical;seconds_sum+=elapsed
   assert bytes_sum==r['logical_bytes'] and abs(seconds_sum-r['job_wall_s'])<1e-10
 summary=[]
 for name in sorted({x['strategy'] for x in records}):
  for phase in range(1,5):
   values=[x for x in records if x['strategy']==name and x['phase']==phase]
   assert len(values)==12
   summary.append(dict(strategy=name,phase=phase,n=12,mib_s=statistics.mean(x['mib_s'] for x in values),elapsed_s=statistics.mean(x['elapsed_s'] for x in values)))
 return dict(description='Post-hoc descriptive four-phase hot-shift accounting; no significance claims; boundaries are offline analysis only, not policy inputs. Each phase includes the gap after the previous phase; phase four includes final foreground tail, so bytes and elapsed time sum to full runs.',summary=summary,records=records)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--main',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 a.output.write_text(json.dumps(analyze(a.main),indent=2)+'\n')
