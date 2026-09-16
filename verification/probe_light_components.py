"""Identify which source creates the unrealistic reflection before tuning it."""
import json,sys
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy,domain_render,pipe_studio as studio
from domain_profiles import camera_settings
from domain_geometry import BODY_KEYS
from app_model import validate_settings
from fast_pipeline import install
OUT=ROOT/'verification/realism_20260915/light_components';OUT.mkdir(parents=True,exist_ok=True)
(OUT/'REVIEW_ONLY.txt').write_text('Lighting ablation only, not training data.\n')
rows=json.loads((ROOT/'verification/eval_refinement/review_plan.json').read_text())['samples']
row=deepcopy(next(r for r in rows if r['setup']=='CAM7650' and len(r['instances'])==1 and r['instances'][0].get('spec',{}).get('defect_style')=='SOFT_BUCKLE'))
body={k:row['settings'][k] for k in BODY_KEYS}
row['settings']=validate_settings({**row['settings'],**camera_settings('CAM7650'),**body,'samples':96});row['fixture_parameters']=None
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
original=domain_render.refine_brass
def refine(mat,p):
    original(mat,p)
    if mode=='NoKey':bpy.data.objects['PS_Key'].data.energy=0
    if mode=='NoFill':bpy.data.objects['PS_Fill'].data.energy=bpy.data.objects['PS_Bounce'].data.energy=0
    if mode=='NoRim':bpy.data.objects['PS_Rim'].data.energy=0
domain_render.refine_brass=refine
results=[]
for mode in ('NoKey','NoFill','NoRim'):
    row['sample_id']='component_'+mode
    results.append(domain_render.render_sample(studio,scene,row,OUT/'all'))
    domain_render.atomic_json(OUT/'results.json',results)
