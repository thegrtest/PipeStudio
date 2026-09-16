"""Prepare a small native-resolution check of narrow and mixed defects in every setup."""
import sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from domain_plan import make_plan,SETUPS,validate_domain_plan
from domain_render import atomic_json
from generate_domain_dataset import source_signature,plan_hash

output=ROOT.parent/'BrassDomainNativeMatched_20260914'
if output.exists() and any(output.iterdir()): raise ValueError('Use a new output folder.')
plan=make_plan(seed=914270000,quality='full',preview=True)
selected=[]
for setup in SETUPS:
    rows=[r for r in plan['samples'] if r['setup']==setup]
    selected.append(next(r for r in rows if len(r['instances'])==1 and r['primary_kind']=='FOLD' and r['size_bin']=='small'))
    selected.append(next(r for r in rows if r['primary_kind']=='SOAP_STAIN' and len(r['instances'])==2))
plan['samples']=selected
plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in selected))
plan['expected_instance_counts']=dict(Counter(i['kind'] for r in selected for i in r['instances']))
plan['expected_setup_counts']=dict(Counter(r['setup'] for r in selected))
validate_domain_plan(plan)
output.mkdir(parents=True)
atomic_json(output/'render_plan.json',plan)
atomic_json(output/'dataset_request.json',{'images':16,'renderer_sources':source_signature(),'plan_sha256':plan_hash(plan)})
(output/'all').mkdir()
(output/'all'/'classes.txt').write_text('Fold\nDent\nSoap stain\nOil stain\n')
print(output)
