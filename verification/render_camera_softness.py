"""Three fixed pipes at three gentle optical softness levels, beauty-only."""
import json,sys,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'verification/camera_softness_20260915'
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'REVIEW_ONLY.txt').write_text('Repeated optical controls; exclude this folder from training/evaluation bundles.\n')
import bpy
import pipe_studio as studio
from domain_render import render_sample,atomic_json
from fast_pipeline import install
from camera_response import configure_camera_response
from domain_profiles import optical_response,optical_reference_width
source=json.loads((ROOT/'verification/microdetail_20260915/all_environments/review_plan.json').read_text())['samples']
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
rows=[];records=[]
for setup in ('CAM5080','MACHINE','STUDIO'):
    base=next(r for r in source if r['setup']==setup and r['primary_kind']=='FOLD' and r.get('pair_role')!='lighting_variant')
    for label,softness in (('reference',0.),('gentle',.4),('slightly_soft',.75)):
        row=deepcopy(base);row['sample_id']+='_'+label
        row['pair_role']='optical_control';row['split']='development';row['camera_softness_band']=label
        row['settings'].update(camera_softness=softness,samples=64)
        rows.append(row)
        record=render_sample(studio,scene,row,OUT/'all')
        p=row['settings'];expected=optical_response(p)['total_sigma_at_reference']*p['resolution']/optical_reference_width(p)
        assert abs(record['camera_response_sigma_px']-expected)<2e-6,(record['camera_response_sigma_px'],expected)
        tree=scene.compositing_node_group;count=len(tree.nodes)
        for _ in range(3):
            configure_camera_response(scene,scene.pipe_studio)
            assert scene.compositing_node_group==tree and len(tree.nodes)==count
            assert abs(scene['pipe_camera_response_sigma_px']-expected)<2e-6
        records.append(record);atomic_json(OUT/'results.json',records)
        print('SOFTNESS_PREVIEW',setup,label,record['camera_response_sigma_px'],flush=True)
atomic_json(OUT/'render_plan.json',dict(samples=rows,purpose='Repeated development controls, not a production dataset'))
from domain_plan import CLASSES
atomic_json(OUT/'all/manifest.json',dict(classes=CLASSES,samples=records))
print('SOFTNESS_PREVIEWS_COMPLETE',flush=True)
