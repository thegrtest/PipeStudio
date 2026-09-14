"""Compare crimp profiles under identical camera, finish and illumination."""
from pathlib import Path
import sys
import bpy
import math
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register();scene=bpy.context.scene
folder=root/'examples'/'tight-crimp';folder.mkdir(exist_ok=True)
for amount,name in [(0,'previous'),(.85,'tight')]:
    studio.apply_settings(scene,dict(defect='NONE',flashlight_index=1,flashlight_layout='SINGLE',
        flashlight_camera='FRONT_45',crimp_tightness=amount,resolution=1600,samples=64))
    r=scene.render;r.use_border=True;r.use_crop_to_border=True
    r.border_min_x=.17;r.border_max_x=.36;r.border_min_y=0;r.border_max_y=.29
    r.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)
    r.use_border=False;r.use_crop_to_border=False
camera=scene.camera
elevation=math.radians(55)
camera.location=(0,-math.sqrt(128)*math.cos(elevation),.505+math.sqrt(128)*math.sin(elevation))
camera.rotation_euler=(Vector((0,0,.505))-camera.location).to_track_quat('-Z','Y').to_euler()
r.use_border=True;r.use_crop_to_border=True
r.filepath=str(folder/'tight_reference_angle_55.png');bpy.ops.render.render(write_still=True)
print('TIGHT_CRIMP_PREVIEW_COMPLETE',flush=True)
