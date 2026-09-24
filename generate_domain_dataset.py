"""Generate camera-matched brass defects with committed, resumable image pairs."""
import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent
CODE_FILES=('domain_profiles.py','domain_plan.py','domain_geometry.py','domain_render.py',
    'generate_domain_dataset.py','geometry.py','pipe_studio.py','app_model.py','brass_material.py',
    'inspection_scene.py','camera_response.py','capture_scene.py','capture_plan.py','scene_presets.py','fast_pipeline.py',
    'brass_realism.py','brass_spectrum.py','brass_microdetail.py','body_gap_plan.py','reference_brass_spectrum.json',
    'sensor_response.py','environment_fields.py','reference_environment_fields.json','glare_guard.py','yolox_profile.py','eval_generation.py',
    'soap_residue.py','defect_visibility.py','capture_variation.py','neck_defect_plan.py','eval_gap_plan.py')


def read_json(path,default=None):
    for attempt in range(10):
        try: return json.loads(Path(path).read_text(encoding='utf-8'))
        except FileNotFoundError: return default
        except (PermissionError,json.JSONDecodeError):
            if attempt==9: raise
            time.sleep(min(.05*2**attempt,.8))


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def source_signature():
    return {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in CODE_FILES}


def check_committed(root,plan,manifest,hash_from=0):
    folder=(root/'all').resolve()
    records=manifest['samples']
    expected=[r['sample_id'] for r in plan['samples']]
    if [r['sample_id'] for r in records]!=expected[:len(records)]:
        raise ValueError('Committed records are not a prefix of the saved plan.')
    if not 0<=hash_from<=len(records):
        raise ValueError('Invalid verified prefix.')
    for row in records[hash_from:]:
        for rel,digest in row['output_sha256'].items():
            path=(folder/rel).resolve()
            if not path.is_relative_to(folder) or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                raise ValueError('Committed file is missing or changed: '+str(path))


@contextmanager
def exclusive(root,name='.domain.lock'):
    with (root/name).open('a+b') as handle:
        if handle.tell()==0: handle.write(b'0');handle.flush()
        handle.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError as exc: raise RuntimeError('This dataset already has an active generator.') from exc
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)


def generate(args):
    from domain_plan import make_plan,validate_domain_plan
    from domain_render import atomic_json
    from runtime_paths import blender_path
    root=args.output.resolve()
    if args.resume:
        plan=read_json(root/'render_plan.json')
        if not plan: raise ValueError('No saved plan to resume.')
        validate_domain_plan(plan)
        request=read_json(root/'dataset_request.json')
        if request['renderer_sources']!=source_signature(): raise ValueError('Renderer changed; choose a new output folder.')
    else:
        if root.exists() and any(root.iterdir()): raise ValueError('Choose a new empty output folder or --resume.')
        if getattr(args,'profile','reference')=='eval-gap':
            from eval_gap_plan import make_plan as make_eval_gap_plan, preview_plan
            plan=(preview_plan(args.seed) if args.preview else
                  make_eval_gap_plan(args.count,args.seed,args.quality))
        else:
            plan=make_plan(total=args.count,seed=args.seed,quality=args.quality,preview=args.preview,profile=getattr(args,'profile','reference'))
        root.mkdir(parents=True,exist_ok=True)
        atomic_json(root/'render_plan.json',plan)
        atomic_json(root/'dataset_request.json',{'images':len(plan['samples']),'renderer_sources':source_signature(),
            'plan_sha256':plan_hash(plan),'primary_classes':dict(Counter(r['primary_kind'] for r in plan['samples'])),
            'setups':dict(Counter(r['setup'] for r in plan['samples'])),'synthetic_only':True})
        (root/'all').mkdir()
        (root/'all'/'classes.txt').write_text('Fold\nDent\nSoap stain\nOil stain\n',encoding='utf-8')
        (root/'all'/'data.yaml').write_text('path: '+(root/'all').as_posix()+'\ntrain: images\n'
            'names:\n  0: Fold\n  1: Dent\n  2: Soap stain\n  3: Oil stain\n',encoding='utf-8')
        (root/'Resume Generation.cmd').write_text('@echo off\n"'+sys.executable+'" "'+str(Path(__file__).resolve())+'" --output "%~dp0." --resume\npause\n')
        (root/'Stop After Current Image.cmd').write_text('@echo off\ntype nul > "%~dp0cancel.flag"\n')
    print('DOMAIN_PLAN_READY',len(plan['samples']),root,flush=True)
    if args.prepare_only:return
    with exclusive(root):
        (root/'cancel.flag').unlink(missing_ok=True)
        completed=lambda:len(read_json(root/'all'/'manifest.json',{'samples':[]})['samples'])
        failures=0
        started=time.monotonic()
        initial=completed()
        previous=read_json(root/'all'/'manifest.json')
        if previous: check_committed(root,plan,previous)
        verified=initial
        while completed()<len(plan['samples']):
            if (root/'cancel.flag').exists():
                atomic_json(root/'progress.json',{'state':'paused','completed':completed(),'total':len(plan['samples'])})
                return
            before=completed()
            # An orphan Blender process may still own a chunk after its
            # supervisor was closed. Wait for it instead of racing its files.
            try:
                with exclusive(root,'.domain-worker.lock'): pass
            except RuntimeError:
                time.sleep(2)
                continue
            with (root/'render.log').open('a',encoding='utf-8') as log:
                command=[str(blender_path()),'-b','--factory-startup','-t',str(args.threads),'--python-exit-code','1',
                    '--python',str(ROOT/'domain_render.py'),'--','--output',str(root),'--chunk',str(args.chunk),
                    '--verified-prefix',str(verified)]
                try:
                    result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=max(600,args.chunk*90),
                        creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                except subprocess.TimeoutExpired:
                    result=None
            after=completed()
            # Verify newly committed rows once. A new resume command and final
            # review still hash every output, without quadratic chunk reads.
            current=read_json(root/'all'/'manifest.json')
            if current: check_committed(root,plan,current,hash_from=verified)
            verified=after
            failures=failures+1 if after==before else 0
            elapsed=time.monotonic()-started
            atomic_json(root/'progress.json',{'state':'rendering','completed':after,'total':len(plan['samples']),
                'supervisor_pid':os.getpid(),'images_per_hour':round((after-initial)*3600/max(1,elapsed),1),
                'consecutive_failures':failures})
            print('DOMAIN_COMMITTED',after,'/',len(plan['samples']),flush=True)
            if failures>=3:
                atomic_json(root/'progress.json',{'state':'failed','completed':after,'total':len(plan['samples']),
                    'error':'Three worker attempts made no progress; see render.log.'})
                raise RuntimeError('Repeated failure. Completed pairs remain committed and resumable.')
        result=subprocess.run([sys.executable,str(ROOT/'domain_review.py'),str(root)],check=False)
        if result.returncode:
            atomic_json(root/'progress.json',{'state':'validation_failed','completed':completed(),'total':len(plan['samples'])})
            raise RuntimeError('Final dataset checks failed; see validation.json.')
        atomic_json(root/'progress.json',{'state':'complete','completed':completed(),'total':len(plan['samples']),
            'elapsed_seconds':round(time.monotonic()-started,1)})
        print('DOMAIN_COMPLETE',root,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--count',type=int,default=3200)
    parser.add_argument('--seed',type=int,default=20260914)
    parser.add_argument('--quality',choices=('quick','full'),default='full')
    parser.add_argument('--profile',choices=('reference','yolox','eval-gap'),default='yolox')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--threads',type=int,default=8)
    parser.add_argument('--chunk',type=int,default=20)
    generate(parser.parse_args())
