from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
from app_model import validate_settings
studio.register();scene=bpy.context.scene
p=validate_settings({**studio.settings_dict(scene.pipe_studio),'defect':'DENT','depth':.09,'seed':42,
    'flashlight_layout':'MIXED','flashlight_count':6,'flashlight_index':1,'flashlight_camera':'FRONT_45',
    'flashlight_capture':'ALL','resolution':1200,'samples':48})
spec=track.force_body_dents(track.make_recipe(p),p,4)
button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
folder=root/'examples/realism-refinement';folder.mkdir(exist_ok=True)
infos=track.export_views(scene,folder/'before','row',p)
track.write_region_dataset(folder/'before',infos)
studio.atomic_json(folder/'before/manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
studio.save_blend(folder/'source.blend')
print('REALISM_BASELINE_SAVED',flush=True)
