"""Register the controls in a saved reference workspace, preserving its scene."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio

studio.register()
scene=bpy.context.scene
if scene.pipe_studio.product_mode=='FLASHLIGHT':
    studio.configure_renderer(scene)
    studio.refresh(scene,geometry=True)
elif 'PS_Pipe' not in bpy.data.objects:
    scene=studio.fresh_scene(); studio.setup_scene(scene)
    studio.apply_settings(scene,studio.SCENE_PRESETS['MACHINE'])
else:
    studio.configure_renderer(scene)
    studio.refresh(scene,geometry=True)
bpy.app.timers.register(studio.arrange_view,first_interval=.4)
studio.atomic_json(ROOT/'blender_runtime.json',{'pid':__import__('os').getpid(),
    'file':bpy.data.filepath,'environment':scene.pipe_studio.environment,'product_mode':scene.pipe_studio.product_mode,
    'device':scene.get('pipe_device'),'ready':True})
print('PIPE_STUDIO_BLENDER_READY',scene.pipe_studio.environment,scene.get('pipe_device'),flush=True)
