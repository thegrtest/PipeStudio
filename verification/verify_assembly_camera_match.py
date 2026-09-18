"""Blender checks for elevated-camera projection and photo-composite wiring."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
from assembly_plan import make_specimen,capture_pose
from assembly_scene import build_scene,pose_scene,PREFIX
from assembly_ui import register

expected=None
for scale,condition in ((1,'good'),(2,'dent')):
    recipe=make_specimen(361000,condition,'CAMERA_MATCHED')
    scene,rig,body=build_scene(recipe,8,scale)
    camera=scene.camera
    assert 30<scene['assembly_camera_elevation_deg']<45
    fingerprint=(tuple(camera.location),tuple(camera.rotation_euler),camera.data.lens,camera.data.shift_x,camera.data.shift_y)
    if expected is None:expected=fingerprint
    assert fingerprint==expected,'Defect class or output scale changed camera framing'
    assert (scene.render.resolution_x,scene.render.resolution_y)==(1920*scale,1200*scale)
    tree=scene.compositing_node_group
    merge=tree.nodes['Assembly camera composite']
    assert merge.inputs['Foreground'].links[0].from_node.name=='PS_CR_Highlights'
    assert merge.inputs['Background'].links[0].from_node.name=='Assembly plate exposure compensation'
    assert bpy.data.objects[PREFIX+'Teal bed'].is_shadow_catcher
    assert not bpy.data.objects[PREFIX+'Teal bed'].visible_glossy
    assert not bpy.data.objects[PREFIX+'Soft oxide fill'].visible_glossy
    receivers=bpy.data.collections[scene['assembly_fill_receiver']]
    for light in scene.objects:
        if 'reflection_bar_index' in light:assert light.light_linking.receiver_collection==receivers
    from assembly_scene import make_assembly
    companion,companion_body=make_assembly(scene,make_specimen(461000,'good','CAMERA_MATCHED'))
    for part in companion.children:assert part.name in receivers.objects,part.name
    assert body.data.materials[0]['assembly_finish_version']=='assembly-camera-patch-finish-1'
    assert scene.render.film_transparent
    centers=[]
    for index in range(3):
        pose_scene(scene,rig,body,recipe,capture_pose(recipe,index))
        point=Vector((rig.location.x-.8,rig.location.y,.667))
        p=world_to_camera_view(scene,camera,point);centers.append((p.x*1920,(1-p.y)*1200))
    for a,b in zip(centers,centers[1:]):
        assert abs(b[0]-a[0]-300)<.02,centers
        assert abs(b[1]-a[1]-49.5)<.02,centers
    for obj in scene.objects:
        if obj.type=='MESH' and 'part_class_id' not in obj and obj.name!=PREFIX+'Teal bed':assert obj.hide_render,obj.name

register(ROOT/'verification'/'assembly_camera_ui_smoke',recipe)
p=scene.assembly_studio
assert p.look=='CAMERA_MATCHED'
for preset in ('CURRENT','FOUR_LINES','BALANCED'):
    p.lighting=preset;p.exposure=.4
    assert scene['assembly_lighting_preset']==preset
    assert abs(tree.nodes['Assembly plate exposure compensation'].inputs['Exposure'].default_value+scene.view_settings.exposure)<1e-5
for look in ('ORIGINAL','REFINED','CAMERA_MATCHED'):
    p.look=look
    assert bpy.ops.assembly.build()=={'FINISHED'}
    assert len([o for o in scene.objects if 'reflection_bar_index' in o])==4
    assert bool(scene.get('assembly_background_source'))==(look=='CAMERA_MATCHED')
print('ASSEMBLY_CAMERA_MATCH_PASSED: class-independent camera, native/2x scaling, photo composite, track corridor, three UI looks and lights')
