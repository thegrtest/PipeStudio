from pathlib import Path
import sys,json
import bpy
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe']);p=studio.settings_dict(scene.pipe_studio)
button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
def render(name):
    folder=root/'examples/groove-light-study'/name
    info=track.export_frame(scene,folder,'row_front_45',p)
    studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[info],samples=[info]))
render('refined-fixture')
# Compare fixture intensity with identical materials, camera and objects.
for obj in list(scene.objects):
    if obj.type!='LIGHT':continue
    if obj.name.startswith(('Broad inspection','Top edge reflection','Rib reflection')):obj.data.energy*=1.35
render('brighter-bars')
for obj in list(scene.objects):
    if obj.type=='LIGHT' and obj.name.startswith(('Broad inspection','Top edge reflection','Rib reflection')):
        obj.location.y*=.7;obj.location.z=.505+(obj.location.z-.505)*.7
        obj.data.energy*=.49;obj.data.size*=.7;obj.data.size_y*=.7
        aim_x=obj.location.x if obj.get('inspection_rib_light') else 0
        obj.rotation_euler=(Vector((aim_x,0,.4))-obj.location).to_track_quat('-Z','Y').to_euler()
render('nearer-bars')
print('GROOVE_LIGHTING_STUDY_COMPLETE',flush=True)
