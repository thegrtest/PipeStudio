from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
from shell_appearance import POLYMER_DEFAULTS
from shell_lighting import LIGHT_DEFAULTS
studio.register();scene=bpy.context.scene
studio.apply_settings(scene,dict(resolution=480,samples=8,flashlight_capture='ALL',inspection_light_distance=1.08,
                                plastic_roughness=.247,groove_polish=.687))
scene.pipe_studio.output_dir=str(root/'verification/photo-recovery-worker')
p=studio.settings_dict(scene.pipe_studio);spec=json.loads(scene['flashlight_recipe'])
folder=studio.launch_job(scene,False)
assert studio.ACTIVE_JOB['process'].wait(timeout=120)==0,(folder/'render.log').read_text()[-2000:]
infos=json.loads((folder/'manifest.json').read_text())['samples']
assert [i['camera_id'] for i in infos]==list(track.CAMERAS)
for info in infos:
    assert info['appearance_version']==6 and info['recipe']==spec
    for key in (*POLYMER_DEFAULTS,*LIGHT_DEFAULTS):assert info['parameters'][key]==p[key],key
    bar=next(x for x in info['lighting'] if x['name'].startswith('Top edge reflection'))
    assert abs(bar['size']-(p['flashlight_count']+1.5)*1.08)<1e-4
    assert all(x['power_watts']==0 for x in info['lighting'] if x['name'].startswith('Rib reflection'))
studio.atomic_json(root/'verification/photo-recovery-worker/result.json',dict(passed=True,job=str(folder),
    views=3,custom_material_and_light_controls_preserved=True,recipe_preserved=True))
print('PHOTO_RECOVERY_WORKER_VERIFIED',flush=True)
