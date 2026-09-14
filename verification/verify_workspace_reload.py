"""Run after open_blender_workspace.py against the distributed saved scene."""
import json
from pathlib import Path
import bpy
import pipe_studio as studio
scene=bpy.context.scene
p=scene.pipe_studio
assert p.product_mode=='FLASHLIGHT' and p.flashlight_layout=='MIXED'
assert 'inspection_settings_PIPE' in scene
pipe=json.loads(scene['inspection_settings_PIPE'])
p.product_mode='PIPE'
assert p.environment==pipe['environment']
assert scene.camera.name=='PS_Camera'
p.product_mode='FLASHLIGHT'
assert p.flashlight_layout=='MIXED'
assert bpy.ops.pipe.environment(preset='TRACK_GRAZING')=={'FINISHED'}
strip=next(o for o in scene.objects if o.get('inspection_flashlight') and o.name.startswith('Right grazing'))
assert abs(strip.location.z-1.15)<1e-5
assert bpy.ops.pipe.condition(kind='SCRATCH')=={'FINISHED'}
assert p.flashlight_surface=='METAL'
p.flashlight_count=2
studio.refresh(scene,True)
assert p.flashlight_index<2
assert scene.camera.data.ortho_scale/p.frame_aspect>=3.8-1e-5
studio.apply_settings(scene,{'depth':0,'flashlight_count':6,'flashlight_layout':'SINGLE'})
spec=json.loads(scene['flashlight_recipe'])
assert all(item['defect'] is None for item in spec['items'])
folder=Path(__file__).resolve().parent/'product-modes'
studio.atomic_json(folder/'reload.json',dict(passed=True,pipe_environment=pipe['environment'],
   checks=['saved mode restoration','retained pipe environment','grazing track geometry','scratch selects metal','row index clamping','small row framing','zero depth clears defects']))
print('WORKSPACE_RELOAD_VERIFIED',flush=True)
