from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as s
from scene_presets import SCENE_PRESETS
s.register(); scene=s.fresh_scene(); s.setup_scene(scene)
folder=ROOT/'verification'/'gods-v3-tuning'; folder.mkdir(exist_ok=True)
for name,changes in [('sharper',dict(roughness=.36,texture_strength=.68,wear=.50,finish_marks=.55,key_power=130,light_softness=.55,fill_power=55)),
                     ('balanced',dict(roughness=.42,texture_strength=.68,wear=.50,finish_marks=.55,key_power=100,light_softness=.9,fill_power=40,ambient_strength=.13,sensor_noise=.018))]:
    s.apply_settings(scene,{**SCENE_PRESETS['GODSLIGHT'],**changes,'resolution':960,'samples':48})
    s.export_frame(scene,folder,name)
print('GODS_COMPARE_READY',flush=True)
