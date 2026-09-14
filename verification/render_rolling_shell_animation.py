"""Render the saved animation with the workstation GPU and per-frame progress."""
from pathlib import Path
import json
import sys
import bpy

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio

folder=root/'examples/rolling-shells'
frames=folder/'frames'
frames.mkdir(exist_ok=True)
scene=bpy.context.scene
transform=scene.view_settings.view_transform
studio.configure_renderer(scene)
scene.view_settings.view_transform=transform
scene.cycles.samples=32
scene.cycles.adaptive_threshold=.025
scene.render.use_persistent_data=True
try:
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame)
        scene.render.filepath=str(frames/f'shell_{frame:04d}.png')
        bpy.ops.render.render(write_still=True)
        studio.atomic_json(folder/'render-status.json',dict(state='rendering',completed=frame,total=scene.frame_end))
    studio.atomic_json(folder/'render-status.json',dict(state='frames_complete',completed=144,total=144))
    print('ROLLING_ANIMATION_FRAMES_COMPLETE',flush=True)
except Exception as exc:
    studio.atomic_json(folder/'render-status.json',dict(state='failed',error=str(exc),frame=scene.frame_current))
    raise
