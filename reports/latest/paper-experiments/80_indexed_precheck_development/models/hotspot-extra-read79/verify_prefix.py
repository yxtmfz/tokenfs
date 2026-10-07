from pathlib import Path
import subprocess,csv,json
r=Path(__file__).resolve().parent;d=r/'prefix';d.mkdir(exist_ok=True)
rows=lambda p:list(csv.DictReader(p.open(),delimiter='\t'))
source=(r/'input.txt').read_text().splitlines();cases=[]
for n in [127,401,806]:
 p=d/f'input-{n}.txt';p.write_text('\n'.join(source[:n])+'\n')
 actions=d/f'policy-{n}.tsv';probes=d/f'probes-{n}.tsv';sieve=d/f'sieve-{n}.tsv'
 subprocess.run([str(r/'probe_replay'),str(p),'lru',str(actions),str(probes)],check=True,capture_output=True,text=True)
 subprocess.run([str(r/'sieve_replay'),str(p),str(sieve)],check=True,capture_output=True,text=True)
 for actual,full in [(actions,r/'probe-actions.tsv'),(probes,r/'past-only-probes.tsv'),(sieve,r/'PoolSIEVE1-model.tsv')]:
  assert rows(actual)==[x for x in rows(full) if int(x['observation'])<=n]
 cases.append(n)
(r/'prefix-verification.json').write_text(json.dumps({'passed':True,'prefix_inputs':3,'arms':9,'cutoffs':cases,'all_request_routes_RAM_evictions_copies_and_nonmutating_past_only_policy_probes_equal_full_prefix':True},indent=2)+'\n')
print('3prefixes,9arms,all action/probe logs passed')
