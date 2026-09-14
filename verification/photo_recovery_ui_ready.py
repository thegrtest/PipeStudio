from pathlib import Path
import json,bpy,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipe_studio as studio
from shell_appearance import appearance_settings
from shell_lighting import LIGHT_PRESETS
def verify_settings(p):
    for key,value in {**appearance_settings('REFERENCE'),**LIGHT_PRESETS['PHOTO']}.items():
        # Blender FloatProperty stores float32, including the light angle.
        assert (abs(p[key]-value)<5e-6 if isinstance(value,float) else p[key]==value),(key,p[key],value)

def ready():
    scene=bpy.context.scene;p=studio.settings_dict(scene.pipe_studio)
    assert not bpy.app.background and bpy.ops.pipe.shell_lighting.poll()
    verify_settings(p)
    assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in json.loads(scene['flashlight_recipe'])['defects'])==4
    studio.atomic_json(Path(__file__).resolve().parents[1]/'examples/reference-recovery/ui-ready.json',dict(
        ready=True,file=bpy.data.filepath,preset='REFERENCE',lighting='PHOTO',body_dents=4,
        camera=p['flashlight_camera'],capture=p['flashlight_capture']))
    print('PHOTO_RECOVERY_UI_READY',flush=True)
    return None
if bpy.app.background:
    studio.register()
    verify_settings(studio.settings_dict(bpy.context.scene.pipe_studio))
    print('PHOTO_RECOVERY_SAVED_SETTINGS_VERIFIED',flush=True)
else:
    bpy.app.timers.register(ready,first_interval=3)
