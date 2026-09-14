"""Render and check the exterior center-button refinement with real exports."""
from pathlib import Path
import sys
import json
import math
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track
studio.register();scene=bpy.context.scene
folder=root/'examples'/'button-detail';folder.mkdir(exist_ok=True)
studio.apply_settings(scene,dict(defect='NONE',flashlight_layout='SINGLE',flashlight_index=0,
    flashlight_region='BRASS_FACE',flashlight_camera='FRONT_45',flashlight_capture='ALL',
    crimp_tightness=.85,resolution=1600,samples=64))
r=scene.render
r.use_border=True;r.use_crop_to_border=True
r.border_min_x=.027;r.border_max_x=.19;r.border_min_y=0;r.border_max_y=.325
r.filepath=str(folder/'button_detail.png');bpy.ops.render.render(write_still=True)
r.use_border=False;r.use_crop_to_border=False
infos=button_track.export_views(scene,folder,'clean',studio.settings_dict(scene.pipe_studio))
assert len(infos)==3 and all(not i['annotations'] for i in infos)
button_mats=[]
for obj in scene.objects:
    if obj.get('inspection_region')!='BRASS_FACE':continue
    tree=BVHTree.FromPolygons([v.co for v in obj.data.vertices],[p.vertices for p in obj.data.polygons])
    ys=[]
    for radius in (0,.085,.129,.155,.180):
        hit,normal,index,distance=tree.ray_cast(Vector((radius,-2,0)),Vector((0,1,0)))
        assert hit is not None
        ys.append(hit.y)
    assert ys[0]<ys[1]<ys[2] and ys[3]<ys[2] and ys[3]<ys[4],ys
    assert ys[0]>-1.442,'Button crown must remain behind rolled perimeter'
    mat=obj.data.materials[2];button_mats.append(mat.name)
    shader=mat.node_tree.nodes['Button alloy']
    assert shader.inputs['Roughness'].is_linked,'Configure erased button finish'
    assert any(p.material_index==2 for p in obj.data.polygons)
assert len(set(button_mats))==scene.pipe_studio.flashlight_count
button_track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=infos,samples=infos))
# A center dent still deforms and labels the same Brass Face mesh.
studio.apply_settings(scene,dict(defect='DENT',position=0,depth=.07,width=.08,resolution=480,samples=8))
damaged=button_track.export_views(scene,folder/'dent-check','dent',studio.settings_dict(scene.pipe_studio))
button_track.write_region_dataset(folder/'dent-check',damaged)
studio.atomic_json(folder/'dent-check'/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=damaged,samples=damaged))
front=damaged[0]
assert len(front['annotations'])==1 and front['annotations'][0]['class_id']==1
assert front['annotations'][0]['visible_pixels']>10
face=next(o for o in scene.objects if o.get('inspection_region')=='BRASS_FACE' and o['flashlight_id']==0)
assert face.data.vertices[0].co.y>button_track.button_profile(0)+.03
assert any(p.material_index==1 for p in face.data.polygons)
studio.atomic_json(folder/'button-checks.json',dict(passed=True,clean_views=3,button_materials=button_mats,
    crown_behind_rim=True,center_dent_pixels=front['annotations'][0]['visible_pixels'],
    brass_face_region_preserved=True))
studio.apply_settings(scene,dict(defect='NONE',position=.5,depth=.12,width=.12,resolution=1200,samples=48))
studio.arrange_view()
studio.save_blend(root/'examples'/'button-track'/'Brass Button Track.blend')
print('BUTTON_DETAIL_VERIFIED',flush=True)
