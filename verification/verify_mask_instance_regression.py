"""The shared-mesh-safe label pass must preserve the original row's masks."""
from pathlib import Path
import sys
import json
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene
studio.configure_renderer(scene)
scene.camera=next(obj for obj in scene.objects if obj.get('inspection_camera')=='OVERHEAD')
folder=root/'verification/rolling-mask-regression';folder.mkdir(exist_ok=True)
before={obj.name:[(slot.link,slot.material) for slot in obj.material_slots] for obj in scene.objects if obj.type=='MESH'}
ids=track.mask_pass(scene,folder,'overhead_regions',True)
assert before=={obj.name:[(slot.link,slot.material) for slot in obj.material_slots] for obj in scene.objects if obj.type=='MESH'}
previous=root/'examples/reference-print-study/final'
info=json.loads((previous/'metadata/row_overhead.json').read_text())
for annotation in info['region_annotations']:
    image=bpy.data.images.load(str(previous/annotation['mask']),check_existing=False)
    values=np.empty(len(image.pixels),dtype=np.float32);image.pixels.foreach_get(values)
    expected=values.reshape(ids.shape[0],ids.shape[1],4)[::-1,:,0]>.5
    bpy.data.images.remove(image)
    assert np.array_equal(ids==annotation['instance_id'],expected),annotation['instance_id']
p=studio.settings_dict(scene.pipe_studio)
p['capture_minimum_defect_pixels']=scene.render.resolution_x*scene.render.resolution_y+1
assert track.export_frame(scene,folder,'filtered_out',p) is None
assert not (folder/'images/filtered_out.png').exists()
studio.atomic_json(folder/'validation.json',dict(passed=True,unchanged_region_masks=24,
    material_links_restored=True,filtered_frame_does_not_render_beauty=True))
print('MASK_INSTANCE_REGRESSION_PASSED',flush=True)
