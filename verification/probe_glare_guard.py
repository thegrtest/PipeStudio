"""Small isolated regression render; does not touch active jobs or datasets."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from domain_render import render_sample,atomic_json
from fast_pipeline import install

source=ROOT.parent/'BrassRealismV2_Validated80_20260914'
plan=json.loads((source/'render_plan.json').read_text())
output=ROOT/'verification/glare_guard'
output.mkdir(exist_ok=True)
(output/'REVIEW_ONLY.txt').write_text('Glare correction regression previews. Do not bundle into training data.\n')
# One small fold per setup plus the severe soap/mixed failures and good controls.
offsets=[int(value) for value in sys.argv[sys.argv.index('--')+1:]] if '--' in sys.argv else (1,6,8,0,11,21,31,38,41,45,51,54,61,64,69,60,71)
seeds={914610000+i for i in offsets}
install(studio)
studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
records=json.loads((output/'results.json').read_text()) if (output/'results.json').exists() else []
done={record['sample_id'] for record in records}
for row in plan['samples']:
    if row['settings']['seed'] not in seeds or row['sample_id'] in done: continue
    record=render_sample(studio,scene,row,output/'all')
    records.append(record)
    atomic_json(output/'results.json',records)
    print('GLARE_CHECK',row['sample_id'],record['glare_guard']['retries'],record['glare_guard']['passed'],flush=True)
print('GLARE_COMPLETE',len(records),flush=True)
