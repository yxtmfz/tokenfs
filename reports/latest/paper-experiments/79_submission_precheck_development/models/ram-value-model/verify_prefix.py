from pathlib import Path
import json,subprocess,csv
root=Path(__file__).resolve().parent;folder=root/'prefix';folder.mkdir(exist_ok=True);n=0
for source in sorted((root/'inputs').glob('*.txt')):
 lines=source.read_text().splitlines()
 for cutoff in [127,401,806]:
  prefix=folder/f'{source.stem}-{cutoff}.txt';prefix.write_text('\n'.join(lines[:cutoff])+'\n')
  for mode in ['lru','ranked','marginal']:
   log=folder/f'{source.stem}-{cutoff}-{mode}.tsv'
   subprocess.run([str(root/'replay'),str(prefix),mode,str(log)],capture_output=True,text=True,check=True)
   full=list(csv.DictReader((root/'logs'/f'{source.stem}-{mode}.tsv').open(),delimiter='\t'))
   expected=[row for row in full if int(row['observation'])<=cutoff]
   observed=list(csv.DictReader(log.open(),delimiter='\t'))
   assert expected==observed,(source,cutoff,mode)
   n+=1
(root/'prefix-verification.json').write_text(json.dumps({'passed':True,'cases':n,'arms':n*4,'input_count':10,'all_request_sources_RAM_evictions_disk_copy_decisions_match_full_input_prefix':True,'cutoffs':[127,401,806]},indent=2)+'\n')
print(n,'prefix cases passed')
