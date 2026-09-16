"""Run a saved inspection challenge in background Blender; optionally resume it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import traceback

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import bpy
import pipe_studio as studio
from generation_plan import validate_plan,plan_digest

CODE_FILES=('geometry.py','app_model.py','pipe_studio.py','scene_presets.py','lighting_profiles.py',
            'brass_material.py','brass_finishes.py','brass_realism.py','brass_spectrum.py','brass_microdetail.py','reference_brass_spectrum.json',
            'inspection_scene.py','camera_response.py','generation_plan.py','pipeline_runner.py','mixed_dataset.py')

def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(plan_path,resume=False):
    plan_path=Path(plan_path).resolve(); folder=plan_path.parent
    plan=validate_plan(json.loads(plan_path.read_text(encoding='utf-8')))
    digest=plan_digest(plan)
    code={name:file_hash(ROOT/name) for name in CODE_FILES}
    runtime={'version':bpy.app.version_string,'build_hash':bpy.app.build_hash.decode('ascii','replace')}
    manifest_path=folder/'manifest.json'; completed=[]
    if manifest_path.exists():
        if not resume:
            raise ValueError('Output already has renders; use --resume or choose a new folder.')
        previous=json.loads(manifest_path.read_text(encoding='utf-8'))
        if previous.get('plan_sha256')!=digest or previous.get('renderer_sources')!=code or previous.get('blender_runtime')!=runtime:
            raise ValueError('The plan or renderer code changed. Use a new output folder to avoid mixing versions.')
        completed=previous['samples']
        if [s['sample_id'] for s in completed]!=[s['sample_id'] for s in plan['samples'][:len(completed)]]:
            raise ValueError('Manifest is not a completed prefix of this plan.')
        for sample in completed:
            for relative,expected in sample['output_sha256'].items():
                path=(folder/relative).resolve()
                if not path.is_relative_to(folder) or not path.is_file() or file_hash(path)!=expected:
                    raise ValueError('A completed output is missing or changed: '+relative)
    elif resume:
        raise ValueError('No manifest to resume. Start this plan without --resume.')
    else:
        # Refuse accidental reuse of a populated output folder.
        for sub in ('images','masks','metadata','labels'):
            if (folder/sub).exists() and any((folder/sub).iterdir()):
                raise ValueError('Output contains untracked files: '+sub)
    cancel=folder/'cancel.flag'
    if resume and cancel.exists():
        cancel.unlink()
    manifest={'schema_version':1,'appearance_version':4,'classes':plan['classes'],'seed':plan['seed'],
        'plan_sha256':digest,'renderer_sources':code,'blender_runtime':runtime,'calibrated':False,'purpose':plan['purpose'],
        'independent_specimens':len({s['specimen_id'] for s in plan['samples']}),'samples':completed}
    studio.atomic_json(manifest_path,manifest)
    (folder/'classes.txt').write_text('Fold\nDent\n',encoding='utf-8')
    studio.atomic_json(folder/'source_feature_catalog.json',plan.get('source_feature_catalog'))
    total=len(plan['samples'])
    def status(state,**extra):
        studio.atomic_json(folder/'status.json',{'state':state,'completed':len(completed),'total':total,
            'last_image':str(folder/completed[-1]['image']) if completed else None,**extra})
    try:
        studio.register(); scene=studio.fresh_scene(); studio.setup_scene(scene)
        for item in plan['samples'][len(completed):]:
            if cancel.exists():
                status('cancelled'); return
            status('rendering',current_sample=item['sample_id'])
            studio.apply_settings(scene,item['settings'])
            info=studio.export_frame(scene,folder,item['sample_id'])
            if plan.get('require_visible_defects'):
                if item['settings']['defect']!='NONE' and (not info['bbox_xywh'] or info['visible_mask_pixels']<plan.get('minimum_mask_pixels',1)):
                    raise ValueError('Defect has insufficient visible label support: '+item['sample_id'])
                if item['settings']['defect']=='NONE' and info['bbox_xywh']:
                    raise ValueError('Good pipe unexpectedly has a defect label: '+item['sample_id'])
            info.update({k:v for k,v in item.items() if k!='settings'})
            relative_files=[info['image'],info['mask'],'labels/'+item['sample_id']+'.txt',
                            'metadata/'+item['sample_id']+'.json']
            info['output_sha256']={name:file_hash(folder/name) for name in relative_files}
            completed.append(info); studio.atomic_json(manifest_path,manifest)
            print(f'CHALLENGE_PROGRESS {len(completed)}/{total} {item["sample_id"]}',flush=True)
        # Keep a ready native workspace and both original reference photographs.
        from scene_presets import SCENE_PRESETS
        studio.apply_settings(scene,{**SCENE_PRESETS['MACHINE'],'finish_marks':.22})
        scene.pipe_studio.last_export=str(folder); studio.arrange_view()
        for relative in studio.REFERENCE_PATHS.values():
            ref=bpy.data.images.load(str(ROOT/relative),check_existing=True); ref.pack()
        studio.save_blend(folder/'Inspection Realism V4.blend')
        status('validating')
        python=ROOT/'.venv'/'Scripts'/'python.exe'
        for command in ('validate','coco','report'):
            result=subprocess.run([str(python),str(ROOT/'dataset_tools.py'),command,str(folder)],
                text=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            print(result.stdout,flush=True)
            if result.returncode:
                raise RuntimeError(f'{command} failed: {result.stdout}\n{result.stderr}')
        status('complete',report=str(folder/'report'/'index.html'))
        print('CHALLENGE_READY '+str(folder),flush=True)
    except Exception:
        status('failed',error=traceback.format_exc()); raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',required=True); parser.add_argument('--resume',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    run(args.plan,args.resume)
