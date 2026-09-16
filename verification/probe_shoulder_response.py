"""Test normal continuity of the shoulder, with exported geometry labels."""
import json,sys,time
from pathlib import Path
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import pipe_studio as studio
from domain_render import render_sample,atomic_json
from fast_pipeline import install
from domain_profiles import camera_settings
from domain_geometry import BODY_KEYS
from app_model import validate_settings
OUT=ROOT/'verification/realism_20260915/shoulder_probe'
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'REVIEW_ONLY.txt').write_text('Shoulder normal development controls; exclude from training.\n')
rows=json.loads((ROOT/'verification/eval_refinement/review_plan.json').read_text())['samples']
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
records=[]
for roundness in (.55,.90):
 for camera in ('CAM2534','CAM5080','CAM7650'):
    row=deepcopy(next(r for r in rows if r['setup']==camera and len(r['instances'])==1 and r['instances'][0].get('spec',{}).get('defect_style')=='SOFT_BUCKLE'))
    body={key:row['settings'][key] for key in BODY_KEYS}
    row['settings']=validate_settings({**row['settings'],**camera_settings(camera),**body,'shoulder_roundness':roundness,'samples':96})
    for inst in row['instances']:
        if 'spec' in inst:inst['spec']['shoulder_roundness']=roundness
    row['sample_id']+=f'_round{int(roundness*100)}';row['fixture_parameters']=None
    start=time.perf_counter();record=render_sample(studio,scene,row,OUT/'all')
    records.append(record);atomic_json(OUT/'results.json',records)
    print('SHOULDER_PROBE',roundness,camera,time.perf_counter()-start,flush=True)
