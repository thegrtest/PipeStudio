"""Save production defaults and test a seven-image, two-worker collection."""
from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import rolling_capture as capture
import rolling_quality as quality
studio.register();scene=bpy.context.scene
transform=scene.view_settings.view_transform
studio.configure_renderer(scene);scene.view_settings.view_transform=transform
studio.SUSPENDED=True
try:
    for key,value in quality.PRODUCTION.items():
        if hasattr(scene.pipe_studio,key):setattr(scene.pipe_studio,key,value)
finally:studio.SUSPENDED=False
config=scene.rolling_capture
config.production_quality=True;config.resolution=2400;config.samples=192;config.groove_definition=1.4
config.randomize_defects=True;config.random_seed=51000;config.body_dents=4;config.twist_limit=12
config.start=1;config.end=144;config.step=12;config.camera='ALL';config.trigger='DEFECT'
config.collection_target=3000;config.collection_pass_limit=1000
job={**capture.quality_options(config),'resolution':config.resolution,'samples':config.samples}
p=quality.configure(scene,job);quality.finish_existing(scene,p);quality.scene_view(scene)
scene['rolling_quality_version']=1
scene['rolling_collection_ready']='2400 x 1200, 192 samples, sharp exposure, three cameras, supervised 3000-image target'
scene.frame_set(1)
scene.camera=next(obj for obj in scene.objects if obj.get('inspection_camera')=='FRONT_45')
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
# A bounded production-quality test exercises a worker restart and exact target stopping.
config.end=25;config.step=24;config.trigger='ALL';config.collection_target=7;config.collection_pass_limit=3
folder=capture.launch(scene,autonomous=True)
studio.atomic_json(root/'examples/rolling-shells/quality-collection-preflight.json',dict(folder=str(folder),
    supervisor_pid=capture.ACTIVE['process'].pid,target=7,production_target=3000))
config.end=144;config.step=12;config.trigger='DEFECT';config.collection_target=3000;config.collection_pass_limit=1000
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
print('QUALITY_COLLECTION_PREFLIGHT_STARTED',folder,flush=True)
