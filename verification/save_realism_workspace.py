"""Save a representative mixed row with moderate torsion and a shallow dent."""
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
    'flashlight_capture':'ALL','resolution':1200,'samples':48,'body_twist':35.,'body_twist_span':.7})
spec=track.make_recipe(p)
for index,values in [(1,dict(defect='TWIST',body_twist=35.,body_twist_span=.7)),
                     (2,dict(defect='DENT',depth=.015,width=.14,arc=40.,defect_style='DEFAULT'))]:
    selected=track.make_recipe({**p,**values,'flashlight_layout':'SINGLE','flashlight_index':index,'flashlight_region':'BODY'})
    spec['items'][index]['defect']=selected['items'][index]['defect']
spec['defects']=[i['defect'] for i in spec['items'] if i['defect']]
spec['next_shell_index']=0
button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
assert json.loads(scene['flashlight_recipe'])==spec
folder=root/'examples/defect-realism-study/mixed-preview';folder.mkdir(exist_ok=True)
info=track.export_frame(scene,folder,'mixed_front_45',studio.settings_dict(scene.pipe_studio))
track.write_region_dataset(folder,[info])
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[info],samples=[info]))
scene.pipe_studio.output_dir=str(root/'exports')+'/'
studio.arrange_view();studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
print('REALISM_WORKSPACE_SAVED',flush=True)
