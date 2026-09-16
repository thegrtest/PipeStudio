"""Controlled light-direction experiment, using the real exporter unchanged."""
import sys,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
import pipe_studio as studio
from fast_pipeline import install
import domain_render
from domain_profiles import camera_settings,CAMERAS
from domain_plan import BODY_KEYS
from app_model import validate_settings
OUT=ROOT/'verification'/'realism_v2'/'fill_elevation'
old=json.loads((ROOT.parent/'BrassDomainNativeMatched_20260914'/'render_plan.json').read_text())
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
original=domain_render.refine_brass
tilt=0
def refine(mat,p):
    original(mat,p)
    side=-1 if p.inspection_camera=='CAM2534' else 1
    alpha=math.radians(tilt)
    light=bpy.data.objects['PS_Fill']
    light.location=(0,-6*math.cos(alpha),side*6*math.sin(alpha))
    light.rotation_euler=(-light.location).to_track_quat('-Z','Y').to_euler()
domain_render.refine_brass=refine
for camera in CAMERAS:
    for tilt in (35,55,75):
        row=next(r.copy() for r in old['samples'] if r['setup']==camera)
        p=dict(row['settings']);p.update(camera_settings(camera))
        for key in BODY_KEYS:p[key]=row['settings'][key]
        p.update(resolution=1936,samples=128)
        row['settings']=validate_settings(p);row['sample_id']=f'{camera.lower()}_tilt{tilt}'
        record=domain_render.render_sample(studio,scene,row,OUT/'all')
        domain_render.atomic_json(OUT/f'{row["sample_id"]}.json',record)
        print('FILL_PROBE',camera,tilt,flush=True)
