"""Check the green/cool rig reflection apparent in the horizontal photograph."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as s
from scene_presets import SCENE_PRESETS
s.register();scene=s.fresh_scene();s.setup_scene(scene)
refresh=s.refresh
def reflected_rig(scene,geometry=False):
    refresh(scene,geometry)
    if scene.pipe_studio.environment=='GODSLIGHT':
        for name in ('PS_Key','PS_Fill','PS_Rim'):
            light=bpy.data.objects[name].data
            light.color.r*=.77
            light.color.b*=.93
    bpy.context.view_layer.update()
s.refresh=reflected_rig
s.apply_settings(scene,{**SCENE_PRESETS['GODSLIGHT'],'resolution':1120,'samples':64})
s.export_frame(scene,ROOT/'verification'/'brass-v4'/'color-tuning','green_rig')
