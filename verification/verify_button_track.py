"""Three-camera batch and independent ray-cast checks of visible region masks."""
import json
import sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track
studio.register()
scene=bpy.context.scene
studio.refresh(scene,True)
p=scene.pipe_studio
assert p.environment=='BUTTON_TRACK'
assert len([o for o in scene.objects if o.get('inspection_camera')])==3
assert not any('battery' in o.name.lower() and not o.hide_render for o in scene.objects)
assert len([o for o in scene.objects if o.get('inspection_region')])==p.flashlight_count*4
for obj in scene.objects:
    if obj.get('inspection_region')=='PLASTIC_FACE':
        assert all('plastic' in m.name.lower() for m in obj.data.materials)
folder=root/'verification'/'button-track'
folder.mkdir(exist_ok=True)
studio.apply_settings(scene,{'resolution':480,'samples':8,'defect':'DENT','flashlight_layout':'MIXED','flashlight_capture':'ALL'})
infos=button_track.export_views(scene,folder,'check',studio.settings_dict(p))
assert len(infos)==3 and len({i['specimen_group'] for i in infos})==1
assert {i['camera_id'] for i in infos}==set(button_track.CAMERAS)
assert {d['region'] for d in infos[0]['recipe']['defects']}==set(button_track.REGION_KEYS)
assert infos[0]['recipe']==infos[1]['recipe']==infos[2]['recipe']
checks=[]
for info in infos:
    scene.camera=next(o for o in scene.objects if o.get('inspection_camera')==info['camera_id'])
    cam=scene.camera
    direction=cam.matrix_world.to_3x3()@Vector((0,0,-1))
    expected_z=-1 if info['camera_id']=='OVERHEAD' else -2**-.5
    assert abs(direction.z-expected_z)<1e-5
    w,h=info['width'],info['height']
    ids=np.zeros((h,w),dtype=np.int32)
    for a in info['region_annotations']:
        image=bpy.data.images.load(str(folder/a['mask']),check_existing=False)
        data=np.array(image.pixels[:]).reshape(h,w,4)[::-1,:,0]>.5
        assert not np.any((ids>0)&data),'Region masks overlap'
        ids[data]=a['instance_id']
        bpy.data.images.remove(image)
    total=correct=0
    for y in range(10,h-10,11):
        for x in range(10,w-10,11):
            local=Vector((((x+.5)/w-.5)*cam.data.ortho_scale,(.5-(y+.5)/h)*cam.data.ortho_scale*h/w,0))
            origin=cam.matrix_world@local
            hit,location,normal,index,obj,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,direction)
            if hit and obj.get('inspection_region') and normal.dot(direction)<-.3:
                total+=1;correct+=int(ids[y,x]==obj['region_instance_id'])
    assert total>100 and correct/total>.97,(info['camera_id'],correct,total)
    checks.append(dict(camera=info['camera_id'],matching=correct,tested=total))
button_track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=infos,samples=infos))
studio.apply_settings(scene,{'defect':'NONE'})
clean_faces=[o for o in scene.objects if o.get('inspection_region')=='PLASTIC_FACE']
for obj in clean_faces:
    assert max(v.co.y for v in obj.data.vertices)<=button_track.PLASTIC_RIM_Y+1e-6,'Clean star face protrudes'
    assert max(v.co.y for v in obj.data.vertices)-min(v.co.y for v in obj.data.vertices)>.025,'Fold recess missing'
assert float(button_track._stamp_pixels.max())>.9,'Cap stamp asset missing'
for obj in scene.objects:
    region=obj.get('inspection_region')
    if region=='BODY':
        mat=obj.data.materials[0]
        ink=mat.node_tree.nodes.get('Worn reference body printing')
        assert ink and ink.image.packed_file,'Body printing must be packed in the workspace'
    elif region=='BRASS_FACE':
        assert max((v.co.x*v.co.x+v.co.z*v.co.z)**.5 for v in obj.data.vertices)>.505,'Expanded rim missing'
p.output_dir=str(folder/'batch');p.batch_count=2;p.clean_fraction=1
job=studio.launch_job(scene,True)
assert studio.ACTIVE_JOB['process'].wait(timeout=180)==0,(job/'render.log').read_text()[-4000:]
status=studio.read_status(job)
assert status['completed']==2 and status['rendered_images']==6,status
batch=json.loads((job/'manifest.json').read_text())['samples']
assert len(batch)==6 and all(not i['annotations'] for i in batch)
assert len({i['specimen_group'] for i in batch})==2
assert all(any(a['visible_pixels'] for a in i['region_annotations']) for i in batch)
assert (job/'regions/dataset.yaml').exists() and (job/'regions.coco.json').exists()
studio.atomic_json(folder/'result.json',dict(passed=True,rays=checks,batch=str(job),batch_images=6,
    clean_faces_checked=len(clean_faces),clean_face_protrusion=False))
print('BUTTON_TRACK_VERIFIED',flush=True)
