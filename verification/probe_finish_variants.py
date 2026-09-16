"""Small shader-only comparison, separate from production recipes."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from fast_pipeline import install
import domain_render
from domain_profiles import camera_settings
from domain_plan import BODY_KEYS
from app_model import validate_settings
OUT=ROOT/'verification'/'realism_v2'/'finish_variants'
old=json.loads((ROOT.parent/'BrassDomainNativeMatched_20260914'/'render_plan.json').read_text())
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
original=domain_render.refine_brass
variant=0
def refine(mat,p):
    original(mat,p)
    n=mat.node_tree.nodes;link=mat.node_tree.links.new
    if variant==0:return
    ramp=n['Domain axial alloy color'].color_ramp
    ramp.elements[0].color=(.55,.58,.40,1)
    ramp.elements[1].color=(1.40,1.35,1.28,1)
    n['Domain drawn alloy reflectance'].inputs[0].default_value=.80
    n['Domain axial alloy coordinates'].inputs[1].default_value=(.30,36,36)
    if variant==2:
        fine=n.get('Probe fine color') or n.new('ShaderNodeValToRGB');fine.name='Probe fine color'
        fine.color_ramp.elements[0].position=.25;fine.color_ramp.elements[0].color=(.42,.44,.35,1)
        fine.color_ramp.elements[1].position=.75;fine.color_ramp.elements[1].color=(1.50,1.45,1.25,1)
        link(n['Fine metal grain'].outputs['Fac'],fine.inputs[0])
        mixed=n.get('Probe mixed color') or n.new('ShaderNodeMixRGB');mixed.name='Probe mixed color';mixed.blend_type='MULTIPLY';mixed.inputs[0].default_value=.65
        link(n['Domain drawn alloy reflectance'].outputs[0],mixed.inputs[1]);link(fine.outputs[0],mixed.inputs[2])
        for name in ('BrassShader','PolishedBrass'):link(mixed.outputs[0],n[name].inputs['Base Color'])
domain_render.refine_brass=refine
for variant in range(3):
    row=next(r.copy() for r in old['samples'] if r['setup']=='CAM7650')
    p=dict(row['settings']);p.update(camera_settings('CAM7650'))
    for key in BODY_KEYS:p[key]=row['settings'][key]
    p.update(resolution=1936,samples=128)
    row['settings']=validate_settings(p);row['sample_id']=f'finish_{variant}'
    record=domain_render.render_sample(studio,scene,row,OUT/'all')
    domain_render.atomic_json(OUT/f'finish_{variant}.json',record)
    print('FINISH_VARIANT',variant,flush=True)
