"""Start the authorized production run only after the film has passed verification."""
from pathlib import Path
import json
import sys
import bpy
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
import pipe_studio as studio
import rolling_capture as capture
studio.register(); scene = bpy.context.scene
folder = root / 'examples/rolling-shells/dirty-defect-loop'
report = json.loads((folder/'validation.json').read_text())
assert report['passed'] and (folder/'dirty-defects-rolling-loop.mp4').is_file()
if (folder/'collection.json').exists():
    print('COLLECTION_ALREADY_LAUNCHED', (folder/'collection.json').read_text(), flush=True)
else:
    config = scene.rolling_capture
    assert config.collection_target == 3000 and config.mix_soiling
    assert config.resolution == 2400 and config.samples == 192 and config.camera == 'ALL'
    assert config.random_seed == 61000 and not scene.get('video_only')
    destination = capture.launch(scene, autonomous=True)
    studio.atomic_json(folder/'collection.json', dict(folder=str(destination),
        target_images=3000, supervisor_pid=capture.ACTIVE['process'].pid,
        appearance='clean, light dust, heavy normal dirt', video_verified=True))
    studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
    print('DIRTY_COLLECTION_STARTED', destination, flush=True)
