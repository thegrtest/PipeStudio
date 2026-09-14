"""Render resumable film chunks, verify/encode the loop, then start collection."""
from pathlib import Path
import hashlib
import json
import shutil
import statistics
import subprocess
import sys
import time
from PIL import Image, ImageChops, ImageStat
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from rolling_supervisor import acquire, write
folder = root/'examples/rolling-shells/dirty-defect-loop'
blender = r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe'
lock = acquire(folder)
if lock is None: sys.exit('Video pipeline already running')
frames = folder/'frames'; frames.mkdir(exist_ok=True)
try:
    for start in range(1, 146, 24):
        end = min(145, start+23)
        expected = [frames/f'shell_{frame:04d}.png' for frame in range(start, end+1)]
        if all(path.exists() for path in expected): continue
        for attempt in range(1, 4):
            log = folder/f'render_{start:04d}_{attempt}_{time.time_ns()}.log'
            with log.open('w', encoding='utf-8') as handle:
                command = [blender, '--background', str(folder/'Dirty defect conveyor.blend'),
                    '--python-exit-code', '1', '--python', str(root/'verification/render_dirty_video_frames.py'),
                    '--', str(start), str(end)]
                result = subprocess.run(command, cwd=root, stdout=handle, stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=3600)
            if result.returncode == 0 and all(path.exists() for path in expected): break
        else: raise RuntimeError('Video rendering failed three times; see '+str(log))
    small = []
    for frame in range(1, 146):
        with Image.open(frames/f'shell_{frame:04d}.png') as image:
            assert image.size == (2400, 1200)
            small.append(image.convert('RGB').resize((400, 200)))
    def difference(a, b):
        return statistics.mean(ImageStat.Stat(ImageChops.difference(a, b)).mean)
    adjacent = [difference(a, b) for a, b in zip(small[:144], small[1:144])]
    seam = difference(small[143], small[0]); match = difference(small[144], small[0])
    assert min(adjacent) > .02, 'Frozen animation frame'
    assert seam < statistics.median(adjacent)*2, 'Discontinuous loop'
    assert match < 1., 'Loop geometry or appearance does not return to its initial state'
    ffmpeg, ffprobe = shutil.which('ffmpeg'), shutil.which('ffprobe')
    assert ffmpeg and ffprobe
    video = folder/'dirty-defects-rolling-loop.mp4'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '24',
        '-start_number', '1', '-i', str(frames/'shell_%04d.png'), '-frames:v', '144',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '16', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(video)], check=True)
    probe = json.loads(subprocess.check_output([ffprobe, '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,nb_frames,duration,avg_frame_rate',
        '-of', 'json', str(video)], text=True))['streams'][0]
    assert probe['width'] == 2400 and probe['height'] == 1200 and probe['nb_frames'] == '144'
    assert abs(float(probe['duration'])-6) < .001
    with Image.open(frames/'shell_0001.png') as image:
        image.convert('RGB').save(folder/'poster.jpg', quality=95, subsampling=0)
    write(folder/'validation.json', dict(passed=True, video=probe, median_adjacent_difference=statistics.median(adjacent),
        loop_seam_difference=seam, exact_loop_boundary_difference=match,
        unique_frames=len({hashlib.sha256((frames/f'shell_{f:04d}.png').read_bytes()).hexdigest() for f in range(1,145)})))
    write(folder/'render-status.json', dict(state='video_complete', completed=144, total=144, video=str(video)))
    with (folder/'collection-start.log').open('w', encoding='utf-8') as handle:
        subprocess.run([blender, '--background', str(root/'examples/rolling-shells/Rolling shell capture.blend'),
            '--python-exit-code', '1', '--python', str(root/'verification/start_dirty_collection.py')],
            cwd=root, stdout=handle, stderr=subprocess.STDOUT, check=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    write(folder/'pipeline-status.json', dict(state='collection_started', video=str(video),
        collection=json.loads((folder/'collection.json').read_text())))
    print('VIDEO_VERIFIED_AND_COLLECTION_STARTED', flush=True)
except Exception as exc:
    write(folder/'pipeline-status.json', dict(state='failed', error=str(exc)))
    raise
finally: lock.close()
