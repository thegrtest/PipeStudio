"""One bounded RGB-only video worker; complete frames are safe to resume."""
from pathlib import Path
import json
import os
import sys
import time
import bpy
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
import pipe_studio as studio
import rolling_quality as quality
studio.register(); scene = bpy.context.scene
transform = scene.view_settings.view_transform
studio.configure_renderer(scene); scene.view_settings.view_transform = transform
quality.configure(scene, quality.PRODUCTION)
scene.render.use_persistent_data = True
scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGB'
folder = root / 'examples/rolling-shells/dirty-defect-loop'
frames = folder / 'frames'; frames.mkdir(exist_ok=True)
start, end = map(int, sys.argv[sys.argv.index('--')+1:])
for frame in range(start, end + 1):
    destination = frames / f'shell_{frame:04d}.png'
    if destination.exists(): continue
    scene.frame_set(frame)
    temporary = frames / f'shell_{frame:04d}.partial.png'
    scene.render.filepath = str(temporary)
    tick = time.monotonic(); bpy.ops.render.render(write_still=True)
    os.replace(temporary, destination)
    studio.atomic_json(folder/'render-status.json', dict(state='rendering', frame=frame,
        completed=len(list(frames.glob('shell_????.png'))), total=145,
        last_frame_seconds=round(time.monotonic()-tick, 2)))
print('DIRTY_VIDEO_CHUNK_COMPLETE', start, end, flush=True)
