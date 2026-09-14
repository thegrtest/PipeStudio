from pathlib import Path
import sys,json,faulthandler
faulthandler.dump_traceback_later(45,repeat=True)
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene;studio.configure_renderer(scene)
print('PRINT_PREVIEW_REGISTERED',flush=True)
original=json.loads(scene['flashlight_recipe'])
studio.apply_settings(scene,dict(plastic_ink_wear=.28,resolution=1200,samples=64,flashlight_camera='REFERENCE'))
print('PRINT_PREVIEW_SCENE_BUILT',flush=True)
assert json.loads(scene['flashlight_recipe'])['items']==original['items']
folder=root/'examples/body-print-study'
for camera in ('REFERENCE','OVERHEAD'):
    scene.camera=next(o for o in scene.objects if o.get('inspection_camera')==camera)
    print('PRINT_PREVIEW_RENDERING',camera,flush=True)
    scene.render.filepath=str(folder/(camera.lower()+'.png'));bpy.ops.render.render(write_still=True)
scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='REFERENCE')
studio.save_blend(folder/'Readable printing preview.blend')
print('READABLE_PRINT_PREVIEW_DONE',flush=True)
faulthandler.cancel_dump_traceback_later()
