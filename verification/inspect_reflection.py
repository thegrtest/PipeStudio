"""Locate the actual shoulder reflection before choosing lamp placement."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import bpy
from mathutils import Vector
import pipe_studio as studio
from domain_profiles import camera_settings
from fast_pipeline import install
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
p=camera_settings('CAM2534');p.update(seed=123,resolution=960,samples=64,defect='NONE',depth=0)
studio.apply_settings(scene,p)
obj=bpy.data.objects['PS_Pipe'];target=Vector((2.72,-.738,0))
vertex=min(list(obj.data.vertices)[:len(obj.data.vertices)//2],key=lambda v:(v.co-target).length)
target=obj.matrix_world@vertex.co
normal=(obj.matrix_world.to_3x3()@vertex.normal).normalized()
view=(scene.camera.location-target).normalized()
direction=2*normal.dot(view)*normal-view
key=bpy.data.objects['PS_Key']
print('REFLECTION_DIAGNOSTIC',list(target),list(normal),list(view),list(direction),'lamp',list(key.location),flush=True)
out=ROOT/'verification'/'realism_v2'/'reflection';out.mkdir(exist_ok=True,parents=True)
positions={'current':key.location.copy(),'specular':target+direction*6,
           'opposite':Vector((-1.7,-4.6,-.2))}
for name,location in positions.items():
    for power in (115,600):
        key.location=location;key.rotation_euler=(target-location).to_track_quat('-Z','Y').to_euler()
        key.data.energy=power
        scene.render.filepath=str(out/(name+'_'+str(power)+'.png'))
        bpy.ops.render.render(write_still=True)
