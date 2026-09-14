"""Compare finish changes and validate masks for both camera projections."""
from pathlib import Path
import sys,json,math
import bpy
import numpy as np
from mathutils import Vector,Matrix
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
folder=root/'examples/realism-refinement'
spec=json.loads(scene['flashlight_recipe'])
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in spec['defects'])==4
p=studio.settings_dict(scene.pipe_studio)
checks=[]
for projection,subdir in [('ORTHO','finish-only'),('PERSP','after')]:
    settings={**p,'flashlight_projection':projection}
    button_row.remember(scene,settings,spec);studio.apply_settings(scene,settings)
    assert json.loads(scene['flashlight_recipe'])==spec
    dest=folder/subdir
    infos=track.export_views(scene,dest,'row',settings)
    track.write_region_dataset(dest,infos)
    studio.atomic_json(dest/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
    for info in infos:
        cam=next(o for o in scene.objects if o.get('inspection_camera')==info['camera_id'])
        direction=cam.matrix_world.to_3x3()@Vector((0,0,-1))
        assert abs(direction.z-(-1 if info['camera_id']=='OVERHEAD' else -math.sqrt(.5)))<1e-5
        w,h=info['width'],info['height']
        ids=np.zeros((h,w),dtype=np.int32)
        for a in info['region_annotations']:
            im=bpy.data.images.load(str(dest/a['mask']),check_existing=False)
            pixels=np.array(im.pixels[:]).reshape(h,w,4)[::-1,:,0]>.5
            assert not np.any((ids>0)&pixels)
            ids[pixels]=a['instance_id'];bpy.data.images.remove(im)
        projection_matrix=cam.calc_matrix_camera(bpy.context.evaluated_depsgraph_get(),x=w,y=h,
            scale_x=scene.render.pixel_aspect_x,scale_y=scene.render.pixel_aspect_y)
        inverse=projection_matrix.inverted()
        total=correct=0
        for y in range(10,h-10,13):
            for x in range(10,w-10,13):
                if ids[y,x]==0 or not np.all(ids[y-1:y+2,x-1:x+2]==ids[y,x]):continue
                ndc=(2*(x+.5)/w-1,1-2*(y+.5)/h)
                near=inverse@Vector((*ndc,-1,1));far=inverse@Vector((*ndc,1,1))
                origin=cam.matrix_world@(near.xyz/near.w)
                end=cam.matrix_world@(far.xyz/far.w)
                ray=(end-origin).normalized()
                hit,location,normal,index,obj,matrix=scene.ray_cast(bpy.context.evaluated_depsgraph_get(),origin,ray)
                if hit and obj.get('inspection_region') and normal.dot(ray)<-.3:
                    total+=1;correct+=int(ids[y,x]==obj['region_instance_id'])
        assert total>100 and correct/total>.98,(projection,info['camera_id'],correct,total)
        checks.append(dict(projection=projection,camera=info['camera_id'],matching=correct,tested=total))
    print('REALISM_COMPARISON_COMPLETE',projection,flush=True)
scene.pipe_studio.output_dir=str(root/'exports')+'/'
studio.arrange_view();studio.save_blend(folder/'refined.blend')
studio.atomic_json(folder/'verification.json',dict(passed=True,body_dents=4,recipe_unchanged=True,rays=checks))
print('REALISM_REFINEMENT_VERIFIED',flush=True)
