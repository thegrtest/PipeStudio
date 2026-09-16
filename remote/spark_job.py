"""Prepare a labeled, supervised capture from the saved rolling scene."""
import argparse
import json
import os
from pathlib import Path
import sys
import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
import pipe_studio as studio
import rolling_capture as capture

parser = argparse.ArgumentParser()
parser.add_argument('--count', type=int, default=3000)
parser.add_argument('--seed', type=int, default=910000)
parser.add_argument('--smoke', action='store_true')
args = parser.parse_args(sys.argv[sys.argv.index('--')+1:])
if not 1 <= args.count <= 100000:
    raise ValueError('Count must be between 1 and 100000')
report = json.loads((root/'.cache/spark-preflight/result.json').read_text())
if not report.get('passed'):
    raise RuntimeError('Run the GPU preflight before starting collection')
os.environ['PIPESTUDIO_CYCLES_BACKEND'] = report['backend']
studio.register()
scene = bpy.context.scene
transform = scene.view_settings.view_transform
studio.configure_renderer(scene)
scene.view_settings.view_transform = transform
prefs = bpy.context.preferences.addons['cycles'].preferences
if scene.cycles.device != 'GPU' or prefs.compute_device_type != report['backend']:
    raise RuntimeError('Renderer must use the GPU backend validated by preflight')
config = scene.rolling_capture
config.production_quality = True
config.resolution = 2400
config.samples = 192
config.groove_definition = 1.4
config.randomize_defects = True
config.random_seed = args.seed
config.body_dents = 4
config.twist_limit = 12
config.mix_soiling = False
config.start = 1
config.end = 1 if args.smoke else 144
config.step = 12
config.camera = 'ALL'
config.trigger = 'ALL' if args.smoke else 'DEFECT'
config.collection_target = 3 if args.smoke else args.count
config.collection_pass_limit = 10000
config.output_dir = str(root/'exports/spark_captures')
studio.SUSPENDED = True
try:
    scene.pipe_studio.dust_amount = 0
    scene.pipe_studio.groove_residue = 0
finally:
    studio.SUSPENDED = False
folder = capture.launch(scene, autonomous=True)
print('SPARK_CAPTURE_STARTED', str(folder), flush=True)
