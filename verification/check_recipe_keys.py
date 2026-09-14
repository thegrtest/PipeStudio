from pathlib import Path
import sys
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_row
from flashlight_capture import varied_settings
studio.register();scene=bpy.context.scene
base=studio.settings_dict(scene.pipe_studio)
try:
    studio.SUSPENDED=True
    for i in range(200):
        p=varied_settings(base,i)
        for k in studio.SPEC_KEYS+studio.EXTRA_KEYS:setattr(scene.pipe_studio,k,p[k])
        actual=studio.settings_dict(scene.pipe_studio)
        assert button_row.key(p)==button_row.key(actual),(i,p,actual)
finally:studio.SUSPENDED=False
print('RECIPE_KEYS_VERIFIED_200',flush=True)
