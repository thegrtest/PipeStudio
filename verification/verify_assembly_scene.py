"""Blender smoke/regression checks for rebuilding and changing lighting."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
from assembly_scene import build_scene,PREFIX
from assembly_plan import make_specimen
from assembly_ui import register

recipe=make_specimen(260915,'good','REFINED','BALANCED')
expected=None
for i in range(3):
    scene,rig,body=build_scene(recipe,8)
    bpy.context.view_layer.update()
    rail=bpy.data.objects[PREFIX+'Upper brass rail']
    bounds=[world_to_camera_view(scene,scene.camera,rail.matrix_world@Vector(p)) for p in rail.bound_box]
    coords=[(round(v.x*1920),round((1-v.y)*1200)) for v in bounds]
    if expected is None:expected=coords
    assert coords==expected,(i,coords,expected)
    assert len([o for o in bpy.data.objects if o.name.startswith(PREFIX+'Upper brass rail')])==1
    assert rail.dimensions.y<50,rail.dimensions[:]
register(ROOT/'verification'/'assembly_ui_smoke',recipe)
p=scene.assembly_studio
assert len([o for o in scene.objects if o.get('part_class_id')==1])==2
for preset in ('CURRENT','FOUR_LINES','BALANCED'):
    p.lighting=preset
    assert scene['assembly_lighting_preset']==preset
    lights=[o for o in scene.objects if 'reflection_bar_index' in o]
    assert len(lights)==4
    for obj in scene.objects:
        if obj.get('part_class_id')==0 and 'end' not in obj.name:
            shader=obj.data.materials[0].node_tree.nodes['BrassShader']
            source=shader.inputs['Roughness'].links[0].from_node.name
            assert ('Assembly reflection width' in source)==(preset!='CURRENT'),source
for look in ('ORIGINAL','REFINED'):
    p.look=look
    assert bpy.ops.assembly.build()=={'FINISHED'}
    assert json.loads(scene['assembly_recipe_json'])['look']==look
    assert len([o for o in scene.objects if o.get('part_class_id')==1])==2
print('ASSEMBLY_SCENE_CHECKS_PASSED: repeated geometry, three presets, two components per assembly, UI rebuild')
