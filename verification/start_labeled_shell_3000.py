"""Launch the current appearance as an isolated 1,000-row / 3,000-image job."""
from datetime import datetime
from pathlib import Path
import json
import subprocess
import sys
import uuid
import bpy

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
from app_model import validate_settings

studio.register()
scene=bpy.context.scene
settings=studio.settings_dict(scene.pipe_studio)
assert settings['environment']=='BUTTON_TRACK' and settings['product_mode']=='FLASHLIGHT'
assert abs(settings['plastic_ink_wear']-.18)<1e-5
settings.update(flashlight_layout='MIXED',flashlight_count=6,flashlight_capture='ALL',
                flashlight_variation='VARIED',flashlight_crops='ON',defect='DENT',
                resolution=1200,samples=64,batch_count=1000,seed=30000,clean_fraction=0.,front_only=True)
settings=validate_settings(settings)
output=root/'exports/shell_dataset_reference_v8_3000'
folder=output/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
folder.mkdir(parents=True,exist_ok=False)
settings['output_dir']=str(output)
job=dict(settings=settings,count=1000,randomize=True,clean_fraction=0.,front_only=True,
         body_dents_per_row=4,source_blend=bpy.data.filepath,appearance_version=8,body_print_version=3)
studio.atomic_json(folder/'job.json',job)
studio.atomic_json(folder/'status.json',dict(state='starting',completed=0,total=1000,rendered_images=0))
with (folder/'render.log').open('w',encoding='utf-8') as log:
    process=subprocess.Popen([bpy.app.binary_path,'--background','--factory-startup','--python-exit-code','1',
        '--python',str(root/'pipe_studio.py'),'--','--job',str(folder/'job.json')],
        cwd=str(root),stdout=log,stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
studio.atomic_json(output/'active_job.json',dict(folder=str(folder),pid=process.pid,rows=1000,
    expected_images=3000,width=1200,height=600,samples=64,body_dents_per_row=4,
    appearance_version=8,body_print_version=3,source_blend=bpy.data.filepath))
print('STARTED_LABELED_3000_IMAGE_CYCLE',folder,process.pid,flush=True)
