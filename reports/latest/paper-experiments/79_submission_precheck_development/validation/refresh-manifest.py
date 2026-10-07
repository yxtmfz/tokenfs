#!/usr/bin/env python3
"""Update the report inventory only after explicitly reviewing archive edits."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p!=root/'archive-manifest.json' and '__pycache__' not in p.parts}
(root/'archive-manifest.json').write_text(json.dumps(dict(format=1,primary_acceptance='11/16; not all passed',submission_precheck_acceptance='3/4; separate implementation diagnostic',files=files),indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(files=len(files))))
