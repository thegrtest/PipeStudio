from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe'])
p={**studio.settings_dict(scene.pipe_studio),'flashlight_projection':'PERSP','light_softness':.25,
   'key_span':.45,'body_twist':25.,'flashlight_capture':'ALL','flashlight_camera':'FRONT_45'}
button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
assert json.loads(scene['flashlight_recipe'])==spec
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in spec['defects'])==4
folder=root/'examples/realism-refinement/final'
infos=track.export_views(scene,folder,'row',p)
track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
scene.pipe_studio.output_dir=str(root/'exports')+'/'
studio.arrange_view()
studio.save_blend(root/'examples/realism-refinement/refined.blend')
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
print('REFINED_INSPECTION_WORKSPACE_SAVED',flush=True)
