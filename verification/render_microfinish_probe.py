"""Compare fixed previous specimens under a revised surface, at native size."""
import argparse,json,sys,time
from copy import deepcopy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
ap.add_argument('--cameras',nargs='+',default=['CAM2534','CAM5080','CAM7650'])
ap.add_argument('--matched',action='store_true')
ap.add_argument('--baseline',action='store_true')
ap.add_argument('--spectrum',action='store_true')
args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
args.output=args.output.resolve()
import bpy
import pipe_studio as studio
import domain_render
from fast_pipeline import install
if args.spectrum:
    import brass_realism
    from brass_spectrum import configure_spectral_grain
    original_finish=brass_realism.configure_drawn_finish
    def finish(mat,p):
        original_finish(mat,p);configure_spectral_grain(mat,p)
    brass_realism.configure_drawn_finish=finish
if args.baseline:
    import importlib.util,brass_realism
    spec=importlib.util.spec_from_file_location('previous_brass',ROOT/'verification/realism_20260915/source_before/brass_realism.py')
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    brass_realism.configure_drawn_finish=previous.configure_drawn_finish
    import inspection_scene,domain_profiles
    for name in ('inspection_scene','domain_profiles'):
        spec=importlib.util.spec_from_file_location('previous_'+name,ROOT/f'verification/realism_20260915/source_before/{name}.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        if name=='inspection_scene':
            inspection_scene._build_inspection_camera=module._build_inspection_camera
            inspection_scene.configure_inspection_camera=module.configure_inspection_camera
        else:domain_profiles.inspection_light_positions=module.inspection_light_positions
old=json.loads((ROOT/'verification/eval_refinement/review_plan.json').read_text())['samples']
args.output.mkdir(parents=True,exist_ok=True)
(args.output/'REVIEW_ONLY.txt').write_text('Fixed development controls; exclude from training and evaluation datasets.\n')
install(studio);studio.register();scene=studio.fresh_scene();studio.setup_scene(scene)
records=[]
for setup in args.cameras:
    row=deepcopy(next(r for r in old if r['setup']==setup and len(r['instances'])==1 and r['instances'][0].get('spec',{}).get('defect_style')=='SOFT_BUCKLE'))
    from brass_microdetail import VERSION
    row['settings']['samples']=128;row['generation_revision']=VERSION
    if args.matched:
        from domain_profiles import camera_settings
        from domain_geometry import BODY_KEYS
        from app_model import validate_settings
        body={key:row['settings'][key] for key in BODY_KEYS}
        row['settings']=validate_settings({**row['settings'],**camera_settings(setup),**body, 'samples':128})
        row['surface_condition']='reference finish';row['fixture_parameters']=None
    start=time.perf_counter()
    record=domain_render.render_sample(studio,scene,row,args.output/'all')
    record['seconds']=round(time.perf_counter()-start,2);records.append(record)
    domain_render.atomic_json(args.output/'results.json',records)
    print('MICROFINISH',setup,record['seconds'],flush=True)
print('MICROFINISH_COMPLETE',flush=True)
