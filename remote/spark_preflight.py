"""Run with Blender to verify actual GPU rendering and OIDN on the Spark."""
import json
import os
from pathlib import Path
import time
import bpy

root = Path(__file__).resolve().parents[1]
folder = root/'.cache/spark-preflight'
folder.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.render.resolution_x = 128
scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.cycles.samples = 8
scene.cycles.use_denoising = True
scene.cycles.denoiser = 'OPENIMAGEDENOISE'
scene.cycles.denoising_use_gpu = True
prefs = bpy.context.preferences.addons['cycles'].preferences
attempts = []
backends = (os.environ['PIPESTUDIO_CYCLES_BACKEND'],) if os.environ.get('PIPESTUDIO_CYCLES_BACKEND') else ('OPTIX', 'CUDA')
for backend in backends:
    try:
        prefs.compute_device_type = backend
        prefs.refresh_devices()
        devices = [device for device in prefs.devices if device.type == backend]
        if not devices:
            raise RuntimeError(f'No {backend} device available')
        for device in prefs.devices:
            device.use = device.type == backend
        scene.cycles.device = 'GPU'
        scene.render.filepath = str(folder/f'{backend.lower()}.png')
        started = time.monotonic()
        bpy.ops.render.render(write_still=True)
        result = dict(passed=True, blender=bpy.app.version_string,
                      backend=backend, devices=[d.name for d in devices],
                      seconds=round(time.monotonic()-started, 3), oidn=True,
                      attempts=attempts)
        (folder/'result.json').write_text(json.dumps(result, indent=2))
        print('SPARK_GPU_PREFLIGHT', json.dumps(result), flush=True)
        break
    except Exception as error:
        attempts.append(dict(backend=backend, error=str(error)))
else:
    (folder/'result.json').write_text(json.dumps(dict(passed=False, attempts=attempts), indent=2))
    raise RuntimeError('No GPU backend passed the render test; CPU fallback is disabled')
