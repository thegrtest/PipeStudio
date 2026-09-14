from pathlib import Path
import sys,json,time,math,statistics
import bpy
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene
start=time.perf_counter()
studio.apply_settings(scene,dict(defect='TWIST',flashlight_layout='SINGLE',flashlight_region='BODY',
    flashlight_index=1,body_twist=35,resolution=480,samples=8,flashlight_capture='ALL'))
full=time.perf_counter()-start
# Independent old-path check of material slots on one full brass face.
face=next(o for o in scene.objects if o.get('inspection_region')=='BRASS_FACE')
for poly in face.data.polygons:
    center=sum((face.data.vertices[k].co for k in poly.vertices),Vector())/len(poly.vertices)
    assert poly.material_index==(2 if math.hypot(center.x,center.z)<.115 else 0)
cap=next(o for o in scene.objects if o.get('inspection_region')=='PLASTIC_FACE' and o['flashlight_id']==1)
pointer=cap.data.as_pointer();times=[]
for _ in range(4):
    old=json.loads(scene['flashlight_recipe'])
    assert bpy.ops.pipe.randomize()=={'FINISHED'}
    new=json.loads(scene['flashlight_recipe'])
    assert [i for i,(a,b) in enumerate(zip(old['items'],new['items'])) if a!=b]==[1]
    assert cap.data.as_pointer()==pointer
    assert abs(cap.rotation_euler.y+math.radians(new['items'][1]['defect']['twist_degrees']))<1e-5
    assert scene['button_row_rebuilt_regions']==1
    times.append(scene['button_row_last_update_seconds'])
folder=root/'verification/twist-updates';folder.mkdir(exist_ok=True)
scene.pipe_studio.output_dir=str(folder/'worker')
job=studio.launch_job(scene,False)
assert studio.ACTIVE_JOB['process'].wait(timeout=180)==0,(job/'render.log').read_text()[-2000:]
infos=json.loads((job/'manifest.json').read_text())['samples']
assert len(infos)==3 and all(info['recipe']==new for info in infos)
assert any(a['class_id']==6 and a['visible_pixels']>0 for info in infos for a in info['annotations'])
studio.atomic_json(folder/'checks.json',dict(passed=True,full_build_seconds=full,local_median_seconds=statistics.median(times),
    plastic_end_mesh_reused=True,material_assignment_equivalent=True,worker=str(job)))
print('TWIST_UPDATES_VERIFIED',flush=True)
