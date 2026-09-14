from pathlib import Path
import sys
import bpy
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track
studio.register()
scene=bpy.context.scene
if 'PS_Pipe' not in bpy.data.objects:studio.setup_scene(scene)
scene.pipe_studio.product_mode='FLASHLIGHT'
bpy.ops.pipe.environment(preset='BUTTON_TRACK')
studio.apply_settings(scene,{'resolution':1200,'samples':48,'flashlight_layout':'MIXED','flashlight_count':6,'depth':.12,'seed':42})
folder=root/'examples'/'button-track'
folder.mkdir(exist_ok=True)
infos=button_track.export_views(scene,folder,'reference',studio.settings_dict(scene.pipe_studio))
button_track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=infos,samples=infos))
saved_defect=scene.pipe_studio.defect
studio.apply_settings(scene,{'defect':'NONE'})
from verification.render_clean_button_track import capture
capture(scene,folder)
studio.apply_settings(scene,{'defect':saved_defect})
studio.arrange_view()
studio.save_blend(folder/'Brass Button Track.blend')
print('BUTTON_TRACK_REFERENCE_COMPLETE',flush=True)
