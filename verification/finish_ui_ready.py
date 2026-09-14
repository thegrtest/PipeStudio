from pathlib import Path
import json,bpy
import pipe_studio as studio
from shell_appearance import POLYMER_DEFAULTS,appearance_settings

def ready():
    scene=bpy.context.scene;p=studio.settings_dict(scene.pipe_studio)
    spec=json.loads(scene['flashlight_recipe'])
    assert not bpy.app.background and bpy.ops.pipe.shell_appearance.poll()
    assert all(p[key]==value for key,value in appearance_settings('REFERENCE').items())
    assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in spec['defects'])==4
    studio.atomic_json(Path(__file__).resolve().parents[1]/'examples/polymer-finish-study/ui-ready.json',dict(
        ready=True,file=bpy.data.filepath,sidebar='Inspection Studio',preset='REFERENCE',
        camera=p['flashlight_camera'],export_cameras=p['flashlight_capture'],body_dents=4,
        controls={key:p[key] for key in POLYMER_DEFAULTS}))
    print('SHELL_FINISH_UI_READY',flush=True)
    return None
bpy.app.timers.register(ready,first_interval=3)
