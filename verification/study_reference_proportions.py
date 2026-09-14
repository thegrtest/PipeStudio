from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe']);base=studio.settings_dict(scene.pipe_studio)
for scale,angle in [(1.,55.),(.94,55.),(1.,60.)]:
    p={**base,'flashlight_camera':'REFERENCE','flashlight_capture':'CURRENT',
       'flashlight_length_scale':scale,'flashlight_reference_elevation':angle}
    button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
    folder=root/'examples/reference-match-study'/f'fit-{scale}-{angle}'
    info=track.export_frame(scene,folder,'row_reference',p)
    studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[info],samples=[info]))
print('REFERENCE_PROPORTIONS_COMPLETE',flush=True)
