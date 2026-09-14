"""Build reference-sized beauty renders and a separately named editable workspace."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from scene_presets import SCENE_PRESETS

studio.register(); scene=studio.fresh_scene(); studio.setup_scene(scene)
folder=ROOT/'examples'/'realism-v2'; folder.mkdir(parents=True,exist_ok=True)
reports=[]
for environment in ('MACHINE','GODSLIGHT'):
    studio.apply_settings(scene,SCENE_PRESETS[environment])
    info=studio.export_frame(scene,folder,environment.lower())
    assert info['width']==SCENE_PRESETS[environment]['resolution']
    assert bool(info['bbox_xywh'])==(environment=='MACHINE')
    assert not scene.get('_ps_camera_response_diagnostic',False)
    reports.append(info)
studio.atomic_json(folder/'manifest.json',{'appearance_version':2,'calibrated':False,'samples':reports})
studio.apply_settings(scene,SCENE_PRESETS['MACHINE'])
studio.arrange_view()
# Retain both originals in the file for convenient native image comparison.
for relative in studio.REFERENCE_PATHS.values():
    ref=bpy.data.images.load(str(ROOT/relative),check_existing=True)
    ref.pack()
studio.save_blend(folder/'Inspection Realism V2.blend')
print('REALISM_V2_READY',str(folder),flush=True)
