from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
studio.register();scene=bpy.context.scene
spec=json.loads(scene['flashlight_recipe']);base=studio.settings_dict(scene.pipe_studio)
for span in (.45,.65):
    p={**base,'light_softness':.25,'key_span':span,'flashlight_capture':'CURRENT'}
    # Only appearance controls vary; the exact four dents remain fixed.
    button_row.remember(scene,p,spec);studio.apply_settings(scene,p)
    dest=root/'examples/realism-refinement'/f'span-{span}'
    info=track.export_frame(scene,dest,'row_front_45',p)
    studio.atomic_json(dest/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[info],samples=[info]))
print('LIGHTING_COMPARISON_COMPLETE',flush=True)
