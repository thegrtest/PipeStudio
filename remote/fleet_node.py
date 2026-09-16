"""SSH/stdin worker agent. Uses no listening server and never needs root."""
import argparse
import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import time

from fleet_common import digest_file, digest_json, inside, read_json, safe_name, write_json


@contextmanager
def lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a+b') as handle:
        if handle.tell()==0: handle.write(b'0'); handle.flush()
        handle.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError('This node already has an active generation worker') from error
        try: yield
        finally:
            handle.seek(0)
            if os.name == 'nt': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(handle, fcntl.LOCK_UN)


def busy(root):
    try:
        with lock(root/'worker.lock'): return False
    except RuntimeError: return True


def cache_runtime_compatible(old, new):
    """A release handoff may change only the explicit RGB cache policy."""
    normalized=[]
    for config in (old,new):
        runtime={k:v for k,v in config.items() if k!='release'}
        env=dict(runtime.get('env',{}))
        if env.pop('PIPESTUDIO_RENDER_CACHE','off') not in ('off','beauty'):
            return False
        if env: runtime['env']=env
        else: runtime.pop('env',None)
        normalized.append(runtime)
    return normalized[0]==normalized[1]


def status(root, job=None):
    job = job or read_json(root/'active.json', {}).get('job')
    certificate = read_json(root/'readiness.json', {})
    installed = read_json(root/'current_release.json', {}).get('release')
    readiness = dict(installed_release=installed,readiness=certificate,
                     source_ready=bool(installed and certificate.get('release')==installed))
    if not job: return dict(state='idle', running=busy(root), completed=0, **readiness)
    folder = root/'jobs'/safe_name(job)
    result = read_json(folder/'fleet_status.json', dict(state='prepared', completed=0))
    result.update(job=job, folder=str(folder), running=busy(root))
    progress = read_json(folder/'progress.json', {})
    if result['running'] and progress.get('completed', 0) > result.get('completed', 0):
        result['completed'] = progress['completed']
        result['total'] = progress.get('total', result.get('total'))
    result['last_image'] = progress.get('last_image')
    if not result['running'] and result['state'] in ('running','starting'):
        result['state'] = 'interrupted'
    result.update(readiness)
    return result


def work(root, job):
    folder = root/'jobs'/safe_name(job)
    request = read_json(folder/'fleet_job.json')
    release = root/'releases'/safe_name(request['release'])
    sys.path.insert(0, str(release))
    from generate_domain_dataset import check_committed
    plan = read_json(folder/'render_plan.json')
    manifest_path = folder/'all/manifest.json'
    started = time.monotonic()
    env = os.environ.copy()
    env.update(request.get('env', {}))
    verified = 0
    failures = 0
    with lock(root/'worker.lock'):
        try:
            for name, expected in read_json(release/'release.json')['files'].items():
                if digest_file(inside(release, name)) != expected:
                    raise ValueError('Render snapshot changed: '+name)
            while True:
                manifest = read_json(manifest_path, {'samples': []})
                check_committed(folder, plan, manifest, hash_from=verified)
                verified = len(manifest['samples'])
                state = 'complete' if verified == len(plan['samples']) else 'running'
                if (folder/'cancel.flag').exists() and state != 'complete': state = 'paused'
                result = dict(state=state, completed=verified, total=len(plan['samples']),
                              pid=os.getpid(), failures=failures, elapsed_seconds=round(time.monotonic()-started,1))
                write_json(folder/'fleet_status.json', result)
                if state != 'running': break
                minimum_free = request.get('minimum_free_gb', 3) * 1024**3
                if shutil.disk_usage(folder).free < minimum_free:
                    raise RuntimeError('Insufficient free disk space; free space and resume this saved job')
                command = [part.replace('{release}',str(release)) for part in request['blender']]+['-b','--factory-startup','-t',str(request.get('threads',8)),
                    '--python-exit-code','1','--python',str(release/'domain_render.py'),'--',
                    '--output',str(folder),'--chunk',str(request.get('chunk',8)),
                    '--verified-prefix',str(verified)]
                with (folder/'render.log').open('a') as log:
                    try:
                        completed = subprocess.run(command, cwd=release, env=env, stdin=subprocess.DEVNULL,
                            stdout=log, stderr=subprocess.STDOUT,
                            timeout=max(900,request.get('chunk',8)*request.get('seconds_per_image',180)),
                            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                        code = completed.returncode
                    except subprocess.TimeoutExpired: code = -999
                after = len(read_json(manifest_path, {'samples': []})['samples'])
                failures = failures+1 if after == verified else 0
                if failures >= 3:
                    raise RuntimeError(f'Three attempts made no progress (last exit {code}); see render.log')
            if state == 'complete':
                with (folder/'validation.log').open('w') as log:
                    reviewed = subprocess.run([sys.executable,str(release/'domain_review.py'),str(folder)],
                        cwd=release, stdout=log, stderr=subprocess.STDOUT)
                if reviewed.returncode: raise RuntimeError('Dataset validation failed; see validation.json')
                write_json(folder/'fleet_status.json', {**result,'validated':True})
        except Exception as error:
            write_json(folder/'fleet_status.json', dict(state='failed', completed=verified,
                       total=len(plan['samples']), error=str(error), pid=os.getpid()))
            raise


def action(root, request):
    action = request['action']
    if action == 'status': return status(root, request.get('job'))
    if action in ('stage_release','install_patch'):
        from release_store import stage, install
        with lock(root/'start.lock'):
            if busy(root): raise RuntimeError('Node is generating; updates are deferred until idle')
            return (stage if action=='stage_release' else install)(root,request)
    if action == 'install':
        if busy(root): raise RuntimeError('Wait for this node to finish before deploying')
        archive_name = request['archive']
        if not archive_name.endswith('.tgz'):
            raise ValueError('Expected a .tgz source archive')
        safe_name(archive_name[:-4])
        archive = root/'incoming'/archive_name
        if digest_file(archive) != request['sha256']: raise ValueError('Source transfer hash mismatch')
        release = root/'releases'/safe_name(request['release'])
        if not (release/'release.json').exists():
            release.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive) as package:
                for member in package:
                    if not (member.isfile() or member.isdir()): raise ValueError('Links are not allowed in source packages')
                    inside(release, member.name)
                    package.extract(member, release, **({'filter':'data'} if hasattr(tarfile,'data_filter') else {}))
        for name, expected in read_json(release/'release.json')['files'].items():
            if digest_file(inside(release,name)) != expected: raise ValueError('Invalid release file: '+name)
        return dict(installed=request['release'])
    job = safe_name(request['job']); folder = root/'jobs'/job
    if action in ('continue_defects','continue_release'):
        with lock(root/'start.lock'):
            if busy(root): raise RuntimeError('Pause the current worker before changing its remaining plan')
            parent=root/'jobs'/safe_name(request['parent_job'])
            if parent==folder: raise ValueError('Continuation must use a new job directory')
            old_plan=read_json(parent/'render_plan.json')
            config=read_json(parent/'fleet_job.json')
            manifest=read_json(parent/'all/manifest.json',{'samples':[]})
            records=manifest['samples']; done=len(records); new_plan=request['plan']
            if manifest.get('plan_sha256') not in (None,digest_json(old_plan)) or records and 'plan_sha256' not in manifest:
                raise ValueError('Parent plan hash differs')
            updated=request['config']; changing_release=action=='continue_release'
            same_runtime=({k:v for k,v in config.items() if k!='release'}=={k:v for k,v in updated.items() if k!='release'})
            if changing_release and not same_runtime:
                same_runtime=cache_runtime_compatible(config,updated)
            if (not same_runtime or not changing_release and config!=updated) or done!=request['completed']:
                raise ValueError('Parent runtime or completion count changed')
            if new_plan['samples'][:done]!=old_plan['samples'][:done]:
                raise ValueError('Committed specimens must not change')
            if [r['sample_id'] for r in new_plan['samples']]!=[r['sample_id'] for r in old_plan['samples']]:
                raise ValueError('Continuation must retain all specimen IDs and their order')
            if [r['sample_id'] for r in records]!=[r['sample_id'] for r in old_plan['samples'][:done]]:
                raise ValueError('Parent commits are not a prefix of the plan')
            if any(r['primary_kind']=='NONE' or not r['instances'] for r in new_plan['samples'][done:]):
                raise ValueError('Every remaining image must contain a defect')
            signature=None
            if changing_release:
                release=root/'releases'/safe_name(updated['release'])
                for name,expected in read_json(release/'release.json')['files'].items():
                    if digest_file(inside(release,name))!=expected: raise ValueError('New release checksum mismatch')
                source=ast.parse((release/'generate_domain_dataset.py').read_text(encoding='utf-8'))
                declaration=next(item.value for item in source.body if isinstance(item,ast.Assign)
                                 and any(isinstance(target,ast.Name) and target.id=='CODE_FILES' for target in item.targets))
                signature={name:digest_file(inside(release,name)) for name in ast.literal_eval(declaration)}
            prepared=globals()['action'](root,dict(action='prepare',job=job,plan=new_plan,config=updated))
            for record in records:
                for relative,expected in record['output_sha256'].items():
                    source=inside(parent/'all',relative); target=inside(folder/'all',relative)
                    if digest_file(source)!=expected: raise ValueError('Existing output hash mismatch')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if not target.exists():
                        temporary=target.with_suffix(target.suffix+'.partial')
                        shutil.copyfile(source,temporary)
                        if digest_file(temporary)!=expected: raise ValueError('Carried output hash mismatch')
                        os.replace(temporary,target)
                    if digest_file(target)!=expected: raise ValueError('Carried output changed')
            if 'plan_sha256' in manifest:
                inherited={**manifest,'plan_sha256':digest_json(new_plan),
                    'continued_from':dict(job=request['parent_job'],plan_sha256=digest_json(old_plan),completed=done)}
                if changing_release:
                    segments=[dict(segment) for segment in manifest.get('source_segments',[])]
                    if not segments:
                        segments=[dict(start=0,end=done,release=config['release'],renderer_sources=manifest['renderer_sources'],blender_runtime=manifest['blender_runtime'])]
                    else:
                        if segments[-1]['end'] is not None: raise ValueError('Expected an open current source segment')
                        segments[-1]['end']=done
                    segments.append(dict(start=done,end=None,release=updated['release'],renderer_sources=signature,
                                         blender_runtime=manifest['blender_runtime'],
                                         runtime_config={k:v for k,v in updated.items() if k!='release'}))
                    inherited.update(renderer_sources=signature,source_segments=segments)
                write_json(folder/'all/manifest.json',inherited)
            write_json(folder/'progress.json',dict(completed=done,total=len(new_plan['samples']),
                last_image=str(folder/'all'/records[-1]['image']) if records else None))
            write_json(folder/'fleet_status.json',dict(state='prepared',completed=done,total=len(new_plan['samples'])))
            if request.get('paused'):
                (folder/'cancel.flag').touch()
                write_json(folder/'fleet_status.json',dict(state='paused',completed=done,total=len(new_plan['samples'])))
                write_json(root/'active.json',dict(job=job))
            return {**prepared,'preserved':done,'remaining_defects':len(new_plan['samples'])-done}
    if action == 'mark_ready':
        state = status(root,job)
        config = read_json(folder/'fleet_job.json')
        if state['running'] or state['state'] != 'complete' or not state.get('validated'):
            raise RuntimeError('A completed, validated render test is required')
        if config['release'] != request['release']:
            raise ValueError('Readiness test used a different release')
        if digest_json({key:value for key,value in config.items() if key!='release'}) != request['runtime_signature']:
            raise ValueError('Readiness runtime settings differ from the test')
        plan=read_json(folder/'render_plan.json')
        required={'FOLD','DENT','SOAP_STAIN','OIL_STAIN'}
        if not request.get('defects_only'): required.add('NONE')
        if plan['quality']!=request['quality'] or not required.issubset({s['primary_kind'] for s in plan['samples']}):
            raise ValueError('Readiness test must cover every required specimen class')
        certificate = dict(release=request['release'],runtime_signature=request['runtime_signature'],
                           job=job,images=state['completed'],quality=request['quality'],checked_at=time.time(),defects_only=request.get('defects_only',False))
        write_json(root/'readiness.json',certificate)
        return certificate
    if action == 'stop':
        if folder.exists(): (folder/'cancel.flag').touch()
        return dict(stop_requested=True, job=job)
    if action == 'prepare':
        if folder.exists():
            if (read_json(folder/'fleet_job.json') == request['config'] and
                    read_json(folder/'render_plan.json') == request['plan']):
                return dict(prepared=job, existing=True)
            raise FileExistsError('Existing job has a different plan or configuration')
        if shutil.disk_usage(root).free < request['config'].get('minimum_free_gb', 3) * 1024**3:
            raise RuntimeError('Node needs at least 3 GB free before preparing a new job')
        folder.mkdir(parents=True)
        write_json(folder/'render_plan.json', request['plan'])
        write_json(folder/'fleet_job.json', request['config'])
        all_dir=folder/'all'; all_dir.mkdir()
        classes=request['plan']['classes']
        (all_dir/'classes.txt').write_text('\n'.join(classes.values())+'\n')
        (all_dir/'data.yaml').write_text('path: '+all_dir.as_posix()+'\ntrain: images\nnames:\n'+
            ''.join(f'  {k}: {json.dumps(v)}\n' for k,v in classes.items()))
        return dict(prepared=job)
    if action in ('start','resume'):
        with lock(root/'start.lock'):
            if busy(root): raise RuntimeError('This node is already generating')
            if not (folder/'fleet_job.json').exists(): raise ValueError('Prepare the job before starting')
            (folder/'cancel.flag').unlink(missing_ok=True)
            write_json(root/'active.json', dict(job=job))
            with (folder/'supervisor.log').open('a') as log:
                child = subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--root',str(root),'--work',job],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                    start_new_session=os.name!='nt', creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            for _ in range(40):
                if child.poll() is not None: raise RuntimeError('Worker exited during launch; see supervisor.log')
                if busy(root): return dict(started=job, pid=child.pid)
                time.sleep(.05)
            raise RuntimeError('Worker did not acquire its lock')
    if action == 'pack':
        if busy(root): raise RuntimeError('Fetch after this node finishes or pauses')
        archive = root/'outgoing'/(job+'.tar.gz'); archive.parent.mkdir(parents=True,exist_ok=True)
        temporary = archive.with_suffix('.tmp')
        with tarfile.open(temporary,'w:gz',compresslevel=1) as package:
            package.add(folder, arcname=job)
        os.replace(temporary,archive)
        return dict(archive=str(archive),sha256=digest_file(archive),job=job)
    raise ValueError('Unknown fleet action')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', type=Path, required=True); parser.add_argument('--work')
    args = parser.parse_args(); root = args.root.expanduser().resolve(); root.mkdir(parents=True,exist_ok=True)
    if args.work: work(root,args.work)
    else:
        try: print(json.dumps(action(root,json.load(sys.stdin))))
        except Exception as error: print(json.dumps(dict(error=str(error)))); sys.exit(1)
