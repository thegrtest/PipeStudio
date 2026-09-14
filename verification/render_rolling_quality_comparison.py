from pathlib import Path
import sys,json,time
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import rolling_quality as quality
studio.register();scene=bpy.context.scene
transform=scene.view_settings.view_transform
studio.configure_renderer(scene);scene.view_settings.view_transform=transform
scene.camera=next(obj for obj in scene.objects if obj.get('inspection_camera')=='FRONT_45')
scene.frame_set(1);scene.render.use_persistent_data=False
folder=root/'examples/rolling-shells/quality-study';folder.mkdir(exist_ok=True)
job={**quality.PRODUCTION}
p=quality.configure(scene,job);quality.finish_existing(scene,p)
scene.render.filepath=str(folder/'production-front.png')
started=time.monotonic();bpy.ops.render.render(write_still=True)
(folder/'render.json').write_text(json.dumps(dict(settings=job,elapsed_seconds=time.monotonic()-started),indent=2))
print('PRODUCTION_QUALITY_PREVIEW_READY',flush=True)
