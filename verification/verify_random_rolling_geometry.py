"""Prove shared clean geometry preserves labels, and save a randomized preview."""
from pathlib import Path
import json
import sys
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import rolling_randomization as randomized
import rolling_capture as capture
import button_track as track
studio.register();scene=bpy.context.scene
transform=scene.view_settings.view_transform
studio.configure_renderer(scene);scene.view_settings.view_transform=transform
example=json.loads((root/'examples/rolling-shells/random-capture-example.json').read_text())
folder=Path(example['folder']);spec=json.loads((folder/'recipes/pass_0000.json').read_text())
before={obj.name:([list(row) for row in obj.matrix_world],obj.data.energy if obj.type=='LIGHT' else obj.data.lens)
        for obj in scene.objects if obj.type in ('LIGHT','CAMERA')}
rigs,_,_=randomized.randomize(scene,studio.settings_dict(scene.pipe_studio),{},recipe=spec)
assert before=={obj.name:([list(row) for row in obj.matrix_world],obj.data.energy if obj.type=='LIGHT' else obj.data.lens)
        for obj in scene.objects if obj.type in ('LIGHT','CAMERA')}
meshes=[child.data for rig in rigs for child in rig.children if child.type=='MESH']
unique=set(meshes)
assert len(unique)<len(meshes)-30
saved_vertices=sum(len(mesh.vertices) for mesh in meshes)-sum(len(mesh.vertices) for mesh in unique)
assert saved_vertices>3000000
scene.frame_set(1)
scene.camera=next(obj for obj in scene.objects if obj.get('inspection_camera')=='FRONT_45')
scene.render.resolution_x=800;scene.render.resolution_y=400
scene.render.use_persistent_data=False
out=root/'verification/random-rolling-geometry';out.mkdir(exist_ok=True)
before_slots={obj.name:[(slot.link,slot.material) for slot in obj.material_slots] for obj in scene.objects if obj.type=='MESH'}
ids=track.mask_pass(scene,out,'optimized_regions',True)
assert before_slots=={obj.name:[(slot.link,slot.material) for slot in obj.material_slots] for obj in scene.objects if obj.type=='MESH'}
info=json.loads((folder/'metadata/rolling_p0000_00001_front_45.json').read_text())
for annotation in info['region_annotations']:
    image=bpy.data.images.load(str(folder/annotation['mask']),check_existing=False)
    values=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(values)
    expected=values.reshape(400,800,4)[::-1,:,0]>.5
    bpy.data.images.remove(image)
    assert np.array_equal(ids==annotation['instance_id'],expected),annotation['instance_id']
# Capturing the saved preview with randomization switched off must preserve its IDs.
assert capture.prepare(scene)[2]['items']==spec['items']
scene.render.resolution_x=1200;scene.render.resolution_y=600;scene.cycles.samples=32
scene.rolling_capture.randomize_defects=True;scene.rolling_capture.passes=3
scene.rolling_capture.random_seed=41000;scene.rolling_capture.end=144;scene.rolling_capture.step=12
scene.rolling_capture.camera='CURRENT';scene.rolling_capture.trigger='DEFECT'
scene.rolling_capture.resolution=1200;scene.rolling_capture.samples=32
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
studio.atomic_json(out/'validation.json',dict(passed=True,unchanged_region_masks=len(info['region_annotations']),
    lights_and_cameras_unchanged=True,material_links_restored=True,unique_meshes=len(unique),
    mesh_objects=len(meshes),shared_vertices_saved=saved_vertices,preview_capture_ids_preserved=True))
print('RANDOM_ROLLING_GEOMETRY_VERIFIED',flush=True)
