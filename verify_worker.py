"""Run with Blender background; validates the actual asynchronous export entry point."""
from pathlib import Path
import json
import sys

root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
import pipe_studio as studio
import bpy

studio.register()
scene=studio.fresh_scene()
studio.setup_scene(scene)
studio.apply_settings(scene,{'resolution':320,'samples':8,'seed':123,'camera_elevation':0})
p=scene.pipe_studio
p.output_dir=str(root/'verification'/'worker')
p.batch_count=3
p.clean_fraction=0
folder=studio.launch_job(scene,True)
proc=studio.ACTIVE_JOB['process']
result=proc.wait(timeout=180)
assert result==0,(result,(folder/'render.log').read_text()[-3000:])
status=studio.read_status(folder)
assert status['state']=='complete',status
manifest=json.loads((folder/'manifest.json').read_text())
assert len(manifest['samples'])==3
assert len(list((folder/'images').glob('*.png')))==3
assert all(s['visible_mask_pixels']>0 for s in manifest['samples'])
assert p.seed==123, 'Worker must not alter the interactive settings'
assert p.defect=='DENT'
# Verify a queued cancellation is handled without rendering an extra specimen.
cancelled=root/'verification'/'cancelled'
cancelled.mkdir(exist_ok=True)
job={'settings':studio.settings_dict(p),'count':2,'randomize':True}
studio.atomic_json(cancelled/'job.json',job)
(cancelled/'cancel.flag').touch()
studio.run_job(cancelled/'job.json')
cancel_status=studio.read_status(cancelled)
assert cancel_status['state']=='cancelled' and cancel_status['completed']==0,cancel_status
studio.atomic_json(root/'verification'/'worker_result.json',{'passed':True,'folder':str(folder),'status':status,'cancel_status':cancel_status})
print('PIPE_WORKER_VERIFIED',folder,flush=True)
