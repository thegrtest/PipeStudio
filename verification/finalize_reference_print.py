"""Readable packed lettering, unchanged specimen geometry and defect labels."""
from pathlib import Path
import sys,json,hashlib
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene;studio.configure_renderer(scene)
original=json.loads(scene['flashlight_recipe'])
def hashes():
    result={}
    for obj in scene.objects:
        if obj.get('inspection_region'):
            co=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',co)
            indices=np.empty(len(obj.data.polygons),dtype=np.int32);obj.data.polygons.foreach_get('material_index',indices)
            result[(obj['flashlight_id'],obj['inspection_region'])]=hashlib.sha256(co.tobytes()+indices.tobytes()).hexdigest()
    return result
before=hashes()
studio.apply_settings(scene,dict(plastic_ink_wear=.18,resolution=1200,samples=8,flashlight_camera='REFERENCE',flashlight_capture='ALL'))
scene.cycles.device='CPU';scene.render.threads_mode='FIXED';scene.render.threads=8
print('READABLE_PRINT_CPU_SCENE_READY',flush=True)
assert hashes()==before
assert json.loads(scene['flashlight_recipe'])['items']==original['items']
for obj in scene.objects:
    if obj.get('inspection_region')=='BODY':
        mat=obj.data.materials[0];nodes=mat.node_tree.nodes
        assert mat['inspection_body_print_version']==3 and 'FEDERAL' in mat['inspection_body_print_text']
        assert nodes['Outward readable cylindrical printing'].inputs[1].default_value<0
        art=nodes['Worn reference body printing'].image
        assert art.packed_file and art.size[:]==(2611,2048)
p=studio.settings_dict(scene.pipe_studio)
folder=root/'examples/reference-print-study/final'
infos=[]
for camera in ('OVERHEAD','REFERENCE'):
    scene.camera=next(o for o in scene.objects if o.get('inspection_camera')==camera)
    infos.append(track.export_frame(scene,folder,'row_'+camera.lower(),p))
def pixels(path):
    im=bpy.data.images.load(str(path),check_existing=False)
    array=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(array)
    bpy.data.images.remove(im);return array
checked=0
previous=root/'examples/body-print-study/final'
for info in infos:
    assert info['appearance_version']==8
    for a in info['annotations']+info['region_annotations']:
        assert np.array_equal(pixels(folder/a['mask']),pixels(previous/a['mask'])),a['mask']
        checked+=1
    assert np.array_equal(pixels(folder/info['mask']),pixels(previous/info['mask']))
track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
studio.SUSPENDED=True
scene.pipe_studio.samples=64
studio.SUSPENDED=False
scene.cycles.samples=64;scene.cycles.device='GPU';scene.render.threads_mode='AUTO'
studio.arrange_view()
studio.save_blend(root/'examples/reference-print-study/Reference print.blend')
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in original['defects'])==4
studio.atomic_json(folder/'verification.json',dict(passed=True,body_print_version=3,packed=True,
    exterior_uv_orientation_correct=True,body_dents=4,recipe_and_geometry_unchanged=True,
    unchanged_individual_masks=checked,unchanged_combined_masks=2,verification_device='CPU',verification_samples=8,saved_render_samples=64))
print('REFERENCE_PRINT_VERIFIED',flush=True)
