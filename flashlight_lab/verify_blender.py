"""Integration checks: clean/hidden labels, determinism, closed shells and UI rebuild."""
import json
import math
import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import flashlight_scene as lab

output=ROOT/'output'/'integration_checks'
output.mkdir(parents=True,exist_ok=True)
assert lab.recipe(42,True)==lab.recipe(42,True)
clean=lab.recipe(999,clean_probability=1)
scene=lab.build_scene(clean,480,8)
assert len([o for o in scene.objects if 'hollow plastic' in o.name])==6
assert all(item['defect'] is None for item in clean['items'])
infos=[]
info=lab.export_frame(scene,clean,output,'clean')
assert info['annotations']==[]
assert (output/'labels'/'clean.txt').read_text()==''
infos.append(info)
hidden=lab.recipe(42,True)
for item in hidden['items']:
    item['roll']=math.pi
scene=lab.build_scene(hidden,480,8)
info=lab.export_frame(scene,hidden,output,'hidden')
assert len(info['annotations'])==4
assert all(a['visible_pixels']==0 and a['bbox_xywh'] is None for a in info['annotations']),info['annotations']
assert (output/'labels'/'hidden.txt').read_text()==''
infos.append(info)
lab.write_json(output/'manifest.json',dict(classes=lab.CLASSES,images=infos))
import blender_controls
bpy.context.scene.flashlight_lab.seed=55
result=bpy.ops.flashlight.rebuild()
assert result=={'FINISHED'}
assert json.loads(bpy.context.scene['flashlight_recipe'])['seed']==55
assert len([o for o in bpy.context.scene.objects if 'hollow plastic' in o.name])==6
bpy.context.scene.flashlight_lab.seed=56
assert bpy.ops.flashlight.rebuild()=={'FINISHED'}
assert len([o for o in bpy.context.scene.objects if 'hollow plastic' in o.name])==6
for obj in bpy.context.scene.objects:
    if obj.type=='MESH' and 'hollow plastic' in obj.name:
        import bmesh
        bm=bmesh.new()
        bm.from_mesh(obj.data)
        assert all(e.is_manifold for e in bm.edges),obj.name
        bm.free()
lab.write_json(output/'checks.json',dict(determinism=True,clean_empty_labels=True,
               hidden_occluded_masks=True,ui_rebuild_twice=True,closed_plastic_shells=True))
print('FLASHLIGHT_INTEGRATION_CHECKS_PASSED')
