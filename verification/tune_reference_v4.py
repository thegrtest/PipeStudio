from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as s
from scene_presets import SCENE_PRESETS
s.register();scene=s.fresh_scene();s.setup_scene(scene)
out=ROOT/'verification'/'brass-v4'/'reference-tuning';out.mkdir(parents=True,exist_ok=True)
refresh=s.refresh;active={}
def refined(scene,geometry=False):
    refresh(scene,geometry)
    p=scene.pipe_studio
    if p.environment=='GODSLIGHT' and active.get('shoulder'):
        key=bpy.data.objects['PS_Key'];key.location.x=p.length*.65
        s.aim(key,(p.length*((p.taper_start+p.taper_end)/2-.5),0,0))
    if active.get('flecks'):
        nodes=bpy.data.materials['PS_Brass'].node_tree.nodes
        nodes['Oxide grain coverage'].inputs[1].default_value=.60
        nodes['Sparse oxide grains'].inputs['From Min'].default_value=.43
        nodes['Sparse oxide grains'].inputs['From Max'].default_value=.64
    bpy.context.view_layer.update()
s.refresh=refined
variants=[('dull',dict(roughness=.53,oxide_amount=.54,polish_amount=.17,texture_strength=.65),{}),
          ('shoulder',dict(roughness=.53,oxide_amount=.54,polish_amount=.17,texture_strength=.65,key_power=125,fill_power=50,rim_power=85,ambient_strength=.13,key_span=.6),{'shoulder':True}),
          ('fine_finish',dict(roughness=.51,oxide_amount=.52,polish_amount=.19,texture_strength=.65,key_power=125,fill_power=50,rim_power=85,ambient_strength=.13,key_span=.6),{'shoulder':True,'flecks':True})]
for name,changes,switches in variants:
    active.clear();active.update(switches)
    s.apply_settings(scene,{**SCENE_PRESETS['GODSLIGHT'],**changes,'resolution':1120,'samples':64})
    s.export_frame(scene,out,name)
print('REFERENCE_TUNING_READY',flush=True)
