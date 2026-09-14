"""Encode the completed loop and verify frame count, duration and continuity."""
from pathlib import Path
import hashlib
import json
import shutil
import statistics
import subprocess
from PIL import Image, ImageChops, ImageStat

root=Path(__file__).resolve().parents[1]
folder=root/'examples/rolling-shells'
frames=[folder/'frames'/f'shell_{frame:04d}.png' for frame in range(1,145)]
assert all(path.exists() for path in frames)
small=[]
for path in frames:
    with Image.open(path) as image:
        assert image.size==(1200,600)
        small.append(image.convert('RGB').resize((200,100)))
def difference(a,b):
    return statistics.mean(ImageStat.Stat(ImageChops.difference(a,b)).mean)
adjacent=[difference(a,b) for a,b in zip(small,small[1:])]
seam=difference(small[-1],small[0])
assert min(adjacent)>.02,'Animation contains frozen frames'
assert seam<statistics.median(adjacent)*2,'Loop boundary changes more than ordinary motion'
ffmpeg=shutil.which('ffmpeg')
ffprobe=shutil.which('ffprobe')
assert ffmpeg and ffprobe
video=folder/'shells-rolling-loop.mp4'
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-framerate','24','-start_number','1',
    '-i',str(folder/'frames'/'shell_%04d.png'),'-frames:v','144','-c:v','libx264','-preset','medium',
    '-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True)
subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(video),
    '-vf','scale=960:480:flags=lanczos','-c:v','libwebp_anim','-quality','78','-loop','0',
    str(folder/'shells-rolling-loop.webp')],check=True)
probe=json.loads(subprocess.check_output([ffprobe,'-v','error','-select_streams','v:0',
    '-show_entries','stream=codec_name,width,height,nb_frames,duration,avg_frame_rate',
    '-of','json',str(video)],text=True))['streams'][0]
assert probe['width']==1200 and probe['height']==600
assert probe['nb_frames']=='144' and abs(float(probe['duration'])-6)<.001
report=dict(passed=True,video=probe,unique_frames=len({hashlib.sha256(path.read_bytes()).hexdigest() for path in frames}),
            median_adjacent_difference=statistics.median(adjacent),loop_seam_difference=seam,
            seam_to_ordinary_motion_ratio=seam/statistics.median(adjacent),
            animation=json.loads((folder/'animation.json').read_text()))
(folder/'validation.json').write_text(json.dumps(report,indent=2))
(folder/'render-status.json').write_text(json.dumps(dict(state='complete',completed=144,total=144,video=str(video)),indent=2))
print(json.dumps(report,indent=2))
