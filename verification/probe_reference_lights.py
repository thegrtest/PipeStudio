"""Finite inspection-lamp ablation; reuses exact specimen/label geometry."""
import json,sys,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
import pipe_studio as studio
import domain_render
from fast_pipeline import install
from domain_profiles import camera_settings
from domain_geometry import BODY_KEYS
from app_model import validate_settings
OUT=ROOT/'verification/realism_20260915/wide_key_probe'
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'REVIEW_ONLY.txt').write_text('Development lighting controls, never training data.\n')
rows=json.loads((ROOT/'verification/eval_refinement/review_plan.json').read_text())['samples']
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
original=domain_render.refine_brass
variant=1
def refine(mat,p):
    original(mat,p)
    key=bpy.data.objects['PS_Key'];side=-1 if p.inspection_camera=='CAM2534' else 1
    shoulder=p.length*((p.taper_start+p.taper_end)/2-.5)
    key.location.z+=side*(3.8 if variant==1 else 2.7)
    key.location.x-=.8
    key.data.size*=1.8 if variant==1 else 1.4
    key.data.size_y*=1.7 if variant==1 else 1.4
    key.rotation_euler=(Vector((shoulder,0,0))-key.location).to_track_quat('-Z','Y').to_euler()
    key.data.energy*=1.05 if variant==1 else .9
    if variant==3:
        key.location=(shoulder+7,-4.6,side*4.5)
        key.data.size=5.5;key.data.size_y=6
        key.data.energy=p.key_power*1.4
        key.rotation_euler=(Vector((shoulder,0,0))-key.location).to_track_quat('-Z','Y').to_euler()
domain_render.refine_brass=refine
records=[]
for variant in (3,):
    for camera in ('CAM2534','CAM5080','CAM7650'):
        row=deepcopy(next(r for r in rows if r['setup']==camera and len(r['instances'])==1 and r['instances'][0].get('spec',{}).get('defect_style')=='SOFT_BUCKLE'))
        row['sample_id']+=f'_light{variant}';row['settings']['samples']=96
        body={k:row['settings'][k] for k in BODY_KEYS}
        row['settings']=validate_settings({**row['settings'],**camera_settings(camera),**body,'samples':96})
        row['fixture_parameters']=None
        start=time.perf_counter();record=domain_render.render_sample(studio,scene,row,OUT/'all')
        record['seconds']=time.perf_counter()-start;records.append(record)
        domain_render.atomic_json(OUT/'results.json',records)
        print('LIGHT_PROBE',variant,camera,record['seconds'],flush=True)
