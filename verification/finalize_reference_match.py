"""Four-view reference fit, independent masks, saved workspace, local updates."""
from pathlib import Path
import sys,json,math
import bpy
import numpy as np
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
from product_modes import FLASHLIGHT_PRESETS
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe']);original_items=spec['items']
p={**studio.settings_dict(scene.pipe_studio),**FLASHLIGHT_PRESETS['Brass button track'],
   'flashlight_length_scale':1.,'flashlight_reference_elevation':55.,'resolution':1200,'samples':64}
button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
spec=json.loads(scene['flashlight_recipe'])
assert spec['version']==12
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in spec['defects'])==4
assert [d['id'] for d in spec['defects']]==[i['defect']['id'] for i in original_items if i['defect']]
folder=root/'examples/reference-match-study/final'
infos=track.export_views(scene,folder,'row',p)
assert [i['camera_id'] for i in infos]==list(track.CAMERAS)
scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='REFERENCE')
infos.append(track.export_frame(scene,folder,'row_reference',{**p,'flashlight_capture':'CURRENT'}))
track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
checks=[]
for info in infos:
    cam=next(o for o in scene.objects if o.get('inspection_camera')==info['camera_id'])
    w,h=info['width'],info['height'];ids=np.zeros((h,w),dtype=np.int32)
    for a in info['region_annotations']:
        im=bpy.data.images.load(str(folder/a['mask']),check_existing=False)
        pixels=np.array(im.pixels[:]).reshape(h,w,4)[::-1,:,0]>.5
        assert not np.any((ids>0)&pixels)
        ids[pixels]=a['instance_id'];bpy.data.images.remove(im)
    angle=90 if info['camera_id']=='OVERHEAD' else (55 if info['camera_id']=='REFERENCE' else 45)
    axis=cam.matrix_world.to_3x3()@Vector((0,0,-1))
    assert abs(axis.z+math.sin(math.radians(angle)))<1e-5
    inv=cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=w,y=h).inverted()
    correct=total=0
    for y in range(10,h-10,15):
        for x in range(10,w-10,15):
            if ids[y,x]==0 or not np.all(ids[y-1:y+2,x-1:x+2]==ids[y,x]):continue
            ndc=(2*(x+.5)/w-1,1-2*(y+.5)/h)
            a=inv@Vector((*ndc,-1,1));b=inv@Vector((*ndc,1,1))
            origin=cam.matrix_world@(a.xyz/a.w);end=cam.matrix_world@(b.xyz/b.w)
            ray=(end-origin).normalized()
            hit,location,normal,index,obj,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,ray)
            if hit and obj.get('inspection_region') and normal.dot(ray)<-.3:
                total+=1;correct+=int(ids[y,x]==obj['region_instance_id'])
    assert total>100 and correct/total>.98,(info['camera_id'],correct,total)
    checks.append(dict(camera=info['camera_id'],correct=correct,tested=total))
scene.pipe_studio.output_dir=str(root/'exports')+'/'
scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='REFERENCE')
studio.arrange_view();studio.save_blend(root/'examples/reference-match-study/Reference matched workspace.blend')
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
# Local clicks must retain four dents and all unaffected shells, lights, cameras.
for _ in range(8):
    old=json.loads(scene['flashlight_recipe'])
    pointers={(o['flashlight_id'],o['inspection_region']):o.as_pointer() for o in scene.objects if o.get('inspection_region')}
    lights={o.name:o.as_pointer() for o in scene.objects if o.type in ('CAMERA','LIGHT')}
    index=button_row.mutate(scene,studio.settings_dict(scene.pipe_studio));new=json.loads(scene['flashlight_recipe'])
    assert [i for i,(a,b) in enumerate(zip(old['items'],new['items'])) if a!=b]==[index]
    assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in new['defects'])==4
    assert lights=={o.name:o.as_pointer() for o in scene.objects if o.type in ('CAMERA','LIGHT')}
    assert all(pointers[(o['flashlight_id'],o['inspection_region'])]==o.as_pointer() for o in scene.objects
               if o.get('inspection_region') and o['flashlight_id']!=index)
studio.apply_settings(scene,{'defect':'NONE','resolution':480,'samples':8,'flashlight_capture':'CURRENT'})
clean=track.export_frame(scene,root/'examples/reference-match-study/clean-check','clean_reference',studio.settings_dict(scene.pipe_studio))
assert not clean['annotations'] and clean['visible_mask_pixels']==0
studio.atomic_json(folder/'verification.json',dict(passed=True,body_dents=4,views=4,standard_export_views=3,
    legacy_recipe_migrated=True,local_updates_checked=8,clean_finish_unlabeled=True,rays=checks))
print('REFERENCE_MATCH_WORKSPACE_VERIFIED',flush=True)
