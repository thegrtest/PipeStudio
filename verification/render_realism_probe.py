"""Render repeatable camera comparisons through the actual dataset exporter."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
if '--old-source' in sys.argv:
    import importlib
    archived=ROOT/'verification'/'realism_v2'/'source_before'
    sys.path.insert(0,str(archived))
    # The GPU helper prepends the live root to sys.path. Pin every archived
    # appearance module before importing it, including modules the UI imports
    # lazily, so the baseline cannot silently mix current and previous code.
    for name in ('app_model','domain_profiles','brass_material','camera_response',
                 'inspection_scene','domain_plan','domain_render','pipe_studio'):
        module=importlib.import_module(name)
        assert Path(module.__file__).resolve().parent==archived.resolve(),(name,module.__file__)
        print('BASELINE_SOURCE',name,module.__file__,flush=True)
import pipe_studio as studio
from fast_pipeline import install
from domain_render import render_sample,atomic_json
from domain_profiles import camera_settings,CAMERAS
from app_model import validate_settings
from domain_plan import BODY_KEYS

ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--cameras',nargs='+',default=list(CAMERAS))
ap.add_argument('--session',default='AUG19');ap.add_argument('--quick',action='store_true')
ap.add_argument('--old-source',action='store_true')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
args.output=args.output.resolve()
old=json.loads((ROOT.parent/'BrassDomainNativeMatched_20260914'/'render_plan.json').read_text())
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
for camera in args.cameras:
    row=next(r for r in old['samples'] if r['setup']==camera)
    # Same defect and random specimen as the old validated image, with the
    # revised camera baseline. Preserved finish controls allow a fair comparison.
    p=dict(row['settings']);p.update(camera_settings(camera) if args.old_source else camera_settings(camera,session=args.session))
    for key in BODY_KEYS:
        p[key]=row['settings'][key]
    p['resolution']=960 if args.quick else 1936;p['samples']=64 if args.quick else 128
    row['settings']=validate_settings(p)
    row['sample_id']=camera.lower()+'_'+args.session.lower()
    record=render_sample(studio,scene,row,args.output/'all')
    atomic_json(args.output/(camera.lower()+'.json'),record)
    print('REALISM_PROBE',camera,record['projected_pipe_bbox_xywh'],flush=True)
