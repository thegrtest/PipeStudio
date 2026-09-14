"""Exercise the same background capture operator exposed in Blender's sidebar."""
from pathlib import Path
import json
import sys
import bpy
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register()
scene=bpy.context.scene
studio.apply_settings(scene,{'resolution':960,'samples':48,'flashlight_layout':'MIXED',
    'flashlight_capture':'ALL','flashlight_variation':'VARIED','flashlight_crops':'ON','seed':123})
p=scene.pipe_studio
p.output_dir=str(root/'examples'/'flashlight-capture');p.batch_count=6;p.clean_fraction=.25
folder=studio.launch_job(scene,True)
studio.atomic_json(root/'verification'/'button-track'/'capture-job.json',dict(folder=str(folder)))
code=studio.ACTIVE_JOB['process'].wait(timeout=600)
assert code==0,(folder/'render.log').read_text()[-5000:]
status=studio.read_status(folder)
assert status['state']=='complete' and status['rendered_images']==18,status
infos=json.loads((folder/'manifest.json').read_text())['images']
assert len({i['specimen_group'] for i in infos})==6
for index in range(0,18,3):
    group=infos[index:index+3]
    assert group[0]['recipe']==group[1]['recipe']==group[2]['recipe']
assert all(info['crops'] for info in infos)
studio.atomic_json(root/'verification'/'button-track'/'capture-result.json',dict(passed=True,folder=str(folder),
    images=len(infos),crops=sum(len(i['crops']) for i in infos),
    styles=sorted({d['style'] for i in infos for d in i['recipe']['defects']}),
    classes=sorted({a['class_name'] for i in infos for a in i['annotations'] if a['visible_pixels']})))
print('FLASHLIGHT_CAPTURE_VERIFIED',flush=True)
