"""Save the reference study and exercise existing labels and local updates."""
from pathlib import Path
import sys,json,hashlib
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe'])
def geometry():
    result={}
    for obj in scene.objects:
        if not obj.get('inspection_region'):continue
        xyz=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',xyz)
        result[obj['region_instance_id']]=hashlib.sha256(xyz.tobytes()).hexdigest()
    return result
before=geometry()
p={**studio.settings_dict(scene.pipe_studio),'key_power':1150.,'rim_power':1150.,
   'flashlight_camera':'FRONT_45','flashlight_capture':'ALL','resolution':1200,'samples':48}
button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
assert geometry()==before,'Normal finish must not alter physical defect geometry'
assert json.loads(scene['flashlight_recipe'])['items']==spec['items']
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in spec['defects'])==4
for obj in scene.objects:
    if obj.get('inspection_region')=='BODY':
        mat=obj.data.materials[0];item=spec['items'][obj['flashlight_id']]
        assert mat['inspection_groove_count']==item['rib_count']
        assert abs(mat['inspection_groove_phase']-item['rib_phase'])<1e-6
        assert obj.data.attributes.get('inspection_rest_position')
        assert all(not n.outputs['Object'].links for n in mat.node_tree.nodes if n.type=='TEX_COORD')
folder=root/'examples/groove-light-study/final'
infos=track.export_views(scene,folder,'row',p);track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
scene.pipe_studio.output_dir=str(root/'exports')+'/'
studio.arrange_view();studio.save_blend(root/'examples/groove-light-study/Groove light reference.blend')
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
# Check the new fixtures and untouched specimens survive an ordinary one-shell update.
objects={o.name:o.as_pointer() for o in scene.objects if o.type in ('CAMERA','LIGHT')}
old=json.loads(scene['flashlight_recipe']);index=button_row.mutate(scene,studio.settings_dict(scene.pipe_studio))
new=json.loads(scene['flashlight_recipe'])
assert [i for i,(a,b) in enumerate(zip(old['items'],new['items'])) if a!=b]==[index]
assert {o.name:o.as_pointer() for o in scene.objects if o.type in ('CAMERA','LIGHT')}==objects
# Clean verification is a separate low-resolution artifact, never the saved workspace.
studio.apply_settings(scene,{'defect':'NONE','resolution':480,'samples':8})
clean=track.export_frame(scene,root/'examples/groove-light-study/clean-check','clean_front_45',studio.settings_dict(scene.pipe_studio))
assert clean['annotations']==[] and clean['visible_mask_pixels']==0
studio.atomic_json(folder/'verification.json',dict(passed=True,physical_geometry_unchanged=True,
    body_dents=4,grooves_match_mesh=True,material_attached_to_deformations=True,
    local_update_one_shell=True,cameras_and_lights_reused=True,normal_finish_unlabeled=True))
print('GROOVE_LIGHT_WORKSPACE_VERIFIED',flush=True)
