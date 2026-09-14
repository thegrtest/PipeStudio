"""Validate aperture pixels and both new conditions through background export."""
from pathlib import Path
import sys,json
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register()
scene=bpy.context.scene
studio.apply_settings(scene,dict(defect='OPEN_CENTER',flashlight_layout='SINGLE',flashlight_index=1,
    flashlight_camera='FRONT_45',flashlight_capture='ALL',resolution=480,samples=8))
p=scene.pipe_studio;p.output_dir=str(root/'verification'/'crimp-batch');p.batch_count=1;p.clean_fraction=0
jobs=[]
for kind,class_id in [('OPEN_CENTER',4),('PROTRUDING_CRIMP',5)]:
    studio.apply_settings(scene,{'defect':kind})
    folder=studio.launch_job(scene,True)
    assert studio.ACTIVE_JOB['process'].wait(timeout=180)==0,(folder/'render.log').read_text()[-3000:]
    status=studio.read_status(folder);assert status['state']=='complete' and status['rendered_images']==3,status
    infos=json.loads((folder/'manifest.json').read_text())['images']
    assert any(a['class_id']==class_id and a['visible_pixels'] for info in infos for a in info['annotations'])
    if kind=='OPEN_CENTER':
        front=next(i for i in infos if i['camera_id']=='FRONT_45')
        # Recreate the exported parameter set to project the aperture independently.
        saved=studio.settings_dict(p)
        studio.apply_settings(scene,front['parameters'])
        proxy=next(o for o in scene.objects if o.get('annotation_only'))
        uv=world_to_camera_view(scene,scene.camera,proxy.matrix_world@proxy.data.vertices[0].co)
        a=front['annotations'][0]
        image=bpy.data.images.load(str(folder/a['mask']),check_existing=False)
        w,h=image.size;x,y=int(uv.x*w),int(uv.y*h)
        assert image.pixels[(y*w+x)*4]>.5,'Visible aperture center missing from defect mask'
        assert proxy.hide_render and proxy.hide_get(),'Annotation geometry visible in beauty'
        bpy.data.images.remove(image)
        studio.apply_settings(scene,saved)
    jobs.append(str(folder))
studio.atomic_json(root/'verification'/'crimp-batch'/'result.json',dict(passed=True,jobs=jobs,images=6,aperture_center_labeled=True))
print('CRIMP_BATCH_VERIFIED',flush=True)
