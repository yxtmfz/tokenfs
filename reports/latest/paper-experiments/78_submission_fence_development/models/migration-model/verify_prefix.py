from pathlib import Path
import subprocess,json,csv
root=Path(__file__).resolve().parent
results=json.loads((root/'results.json').read_text());modes=list(results['rows'][0]['modes']);checks=0
out=root/'prefix-checks';out.mkdir(exist_ok=True)
for stem in ['moving_shared-74801','public_toolagent-74802']:
 source=(root/'inputs'/(stem+'.txt')).read_text().splitlines()
 for cutoff in [127,401,806]:
  p=out/f'{stem}-{cutoff}.txt';p.write_text('\n'.join(source[:cutoff])+'\n')
  for mode in modes:
   log=out/f'{stem}-{cutoff}-{mode}.tsv'
   raw=subprocess.run([str(root/'replay'),str(p),mode,str(log)],check=True,capture_output=True,text=True)
   full=list(csv.DictReader((root/mode/(stem+'.tsv')).open(),delimiter='\t'))
   expected=[r for r in full if int(r['observation'])<=cutoff]
   observed=list(csv.DictReader(log.open(),delimiter='\t'))
   assert expected==observed,(stem,cutoff,mode)
   checks+=1
(root/'prefix-verification.json').write_text(json.dumps({'passed':True,'replay_prefix_checks':checks,'arms':checks*4,'cutoffs':[127,401,806],'inputs':['moving_shared-74801','public_toolagent-74802'],'all_decision_records_equal_full_run_prefix':True},indent=2)+'\n')
print(checks,'prefix checks passed')
