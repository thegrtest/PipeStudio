"""Record that the integrated workspace opened in an interactive Blender window."""
from pathlib import Path
import bpy
import pipe_studio as studio
def ready():
    scene=bpy.context.scene
    studio.atomic_json(Path(__file__).resolve().parent/'product-modes'/'ui-ready.json',{
        'ready':True,'background':bpy.app.background,'windows':len(bpy.context.window_manager.windows),
        'product_mode':scene.pipe_studio.product_mode,'environment':scene.pipe_studio.environment,
        'sidebar':'Inspection Studio','file':bpy.data.filepath})
    return None
bpy.app.timers.register(ready,first_interval=3)
