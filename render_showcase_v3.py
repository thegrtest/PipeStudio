"""Render reference-sized v3 examples independently of the synthetic test set."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent; sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from scene_presets import SCENE_PRESETS
studio.register(); scene=studio.fresh_scene(); studio.setup_scene(scene)
folder=ROOT/'examples'/'realism-v3'; folder.mkdir(parents=True,exist_ok=True)
samples=[]
for environment in ('MACHINE','GODSLIGHT'):
    studio.apply_settings(scene,{**SCENE_PRESETS[environment],'finish_marks':.4 if environment=='GODSLIGHT' else .25})
    samples.append(studio.export_frame(scene,folder,environment.lower()))
studio.atomic_json(folder/'manifest.json',{'classes':{'0':'Fold','1':'Dent'},'appearance_version':3,'calibrated':False,'samples':samples})
print('V3_SHOWCASE_READY '+str(folder),flush=True)
