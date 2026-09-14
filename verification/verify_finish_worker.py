"""Exercise serialization of non-default finish controls into a new renderer."""
from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
from shell_appearance import POLYMER_DEFAULTS
studio.register();scene=bpy.context.scene
studio.apply_settings(scene,dict(resolution=480,samples=8,flashlight_camera='REFERENCE',flashlight_capture='CURRENT',
                                plastic_roughness=.317,plastic_specular=.287,groove_polish=.237,
                                inspection_softness=.63,inspection_scatter=.043))
scene.pipe_studio.output_dir=str(root/'verification/finish-worker')
expected=studio.settings_dict(scene.pipe_studio)
spec=json.loads(scene['flashlight_recipe'])
folder=studio.launch_job(scene,False)
assert studio.ACTIVE_JOB['process'].wait(timeout=120)==0,(folder/'render.log').read_text()[-2000:]
info=json.loads((folder/'manifest.json').read_text())['samples'][0]
assert info['appearance_version']==5 and info['recipe']==spec
for key in POLYMER_DEFAULTS:assert info['parameters'][key]==expected[key],key
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in spec['defects'])==4
studio.atomic_json(root/'verification/finish-worker/result.json',dict(passed=True,job=str(folder),
    custom_controls_preserved=True,defect_recipe_preserved=True,body_dents=4))
print('FINISH_WORKER_VERIFIED',flush=True)
