"""Start the authorized 1,000-row, three-camera production run and return."""
from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register();scene=bpy.context.scene
studio.SUSPENDED=True
try:
    p=scene.pipe_studio
    p.product_mode='FLASHLIGHT';p.environment='BUTTON_TRACK';p.defect='DENT'
    p.flashlight_layout='MIXED';p.flashlight_count=6;p.flashlight_capture='ALL'
    p.flashlight_variation='VARIED';p.flashlight_crops='ON'
    p.resolution=1200;p.samples=48;p.batch_count=1000;p.seed=20000
    p.clean_fraction=.2;p.front_only=True
    p.output_dir=str(root/'exports/shell_dataset_3000')
finally:studio.SUSPENDED=False
folder=studio.launch_job(scene,True)
studio.atomic_json(root/'exports/shell_dataset_3000/active_job.json',dict(folder=str(folder),
    pid=studio.ACTIVE_JOB['process'].pid,rows=1000,expected_images=3000,width=1200,height=600,samples=48))
print('STARTED_3000_IMAGE_CYCLE',folder,studio.ACTIVE_JOB['process'].pid,flush=True)
