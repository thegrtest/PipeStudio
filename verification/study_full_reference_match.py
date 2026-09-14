from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe']);base=studio.settings_dict(scene.pipe_studio)
for name,exposure,power in [('matched',-.60,1500.),('restrained',-.75,1300.)]:
    p={**base,'flashlight_length_scale':1.,'flashlight_reference_elevation':55.,
       'flashlight_camera':'REFERENCE','flashlight_capture':'CURRENT',
       'key_power':power,'rim_power':power,'fill_power':145.,'exposure':exposure,'sensor_noise':.007}
    button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
    folder=root/'examples/reference-match-study'/name
    info=track.export_frame(scene,folder,'row_reference',p)
    studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[info],samples=[info]))
print('FULL_REFERENCE_MATCH_STUDY_COMPLETE',flush=True)
