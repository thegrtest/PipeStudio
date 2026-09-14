"""Inspect the saved rim without rebuilding or changing the workspace file."""
from pathlib import Path
import json
import bpy
root=Path(__file__).resolve().parents[1]
folder=root/'examples'/'rim-detail';scene=bpy.context.scene
scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='FRONT_45')
r=scene.render;r.resolution_x=1600;r.resolution_y=800;r.resolution_percentage=100
scene.cycles.samples=64
r.use_border=True;r.use_crop_to_border=True
r.border_min_x=.02;r.border_max_x=.205;r.border_min_y=0;r.border_max_y=.325
r.filepath=str(folder/'refined_rim.png');bpy.ops.render.render(write_still=True)
errors=[]
for face in (o for o in scene.objects if o.get('inspection_region')=='BRASS_FACE'):
    collar=next(o for o in scene.objects if o.get('inspection_region')=='TOP' and o['flashlight_id']==face['flashlight_id'])
    errors.extend((a.co-b.co).length for a,b in zip(face.data.vertices[-768:],collar.data.vertices[:768]))
assert max(errors)<1e-6
checks=json.loads((folder/'rim-checks.json').read_text())
checks['boundary_vertex_error_max']=max(errors)
(folder/'rim-checks.json').write_text(json.dumps(checks,indent=2))
print('SAVED_RIM_PREVIEW_VERIFIED',flush=True)
