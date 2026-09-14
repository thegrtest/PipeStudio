"""Enable the capture sidebar without rebuilding or moving the rolling scene."""
from pathlib import Path
import sys
import bpy
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
import pipe_studio as studio
if not hasattr(bpy.types.Scene,'pipe_studio'):studio.register()
else:
    import rolling_capture
    rolling_capture.register()
import rolling_capture,rolling_quality
scene=bpy.context.scene
transform=scene.view_settings.view_transform
studio.configure_renderer(scene);scene.view_settings.view_transform=transform
options={**rolling_capture.quality_options(scene.rolling_capture),
         'resolution':scene.rolling_capture.resolution,'samples':scene.rolling_capture.samples}
p=rolling_quality.configure(scene,options)
rolling_quality.finish_existing(scene,p)
rolling_quality.scene_view(scene)
for window in bpy.context.window_manager.windows:
    for area in window.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.show_region_ui=True
            area.spaces.active.region_3d.view_perspective='CAMERA'
print('ROLLING_CAPTURE_CONTROLS_READY',flush=True)
