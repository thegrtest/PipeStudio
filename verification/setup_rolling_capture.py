"""Save the capture workspace and start a bounded three-camera example."""
from pathlib import Path
import sys
import bpy
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
import rolling_capture
studio.register()
scene=bpy.context.scene
config=scene.rolling_capture
config.start=1;config.end=144;config.step=12;config.camera='CURRENT'
config.trigger='DEFECT';config.minimum_pixels=16;config.complete_crops=True
config.resolution=1200;config.samples=32
text=bpy.data.texts.get('Enable Rolling Capture.py') or bpy.data.texts.new('Enable Rolling Capture.py')
text.clear()
text.write('import runpy\nrunpy.run_path('+repr(str(root/'open_rolling_capture.py'))+')\n')
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
config.step=24;config.camera='ALL'
folder=rolling_capture.launch(scene)
config.step=12;config.camera='CURRENT'
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
studio.atomic_json(root/'examples/rolling-shells/capture-example.json',dict(folder=str(folder),
    pid=rolling_capture.ACTIVE['process'].pid,maximum_images=18,cameras=['FRONT_45','REAR_45','OVERHEAD']))
print('ROLLING_CAPTURE_EXAMPLE_STARTED',folder,flush=True)
