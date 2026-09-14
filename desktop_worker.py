"""Persistent Blender render worker, driven only by validated local JSON requests."""
import json
import sys
import time
import traceback
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
import pipe_studio as studio
from app_model import validate_settings
import bpy


def run(session):
    session=Path(session).resolve(); session.mkdir(parents=True,exist_ok=True)
    status=session/'status.json'
    studio.atomic_json(status,{'state':'starting','message':'Starting renderer'})
    studio.register(); scene=studio.fresh_scene(); studio.setup_scene(scene)
    studio.atomic_json(status,{'state':'ready','device':scene.get('pipe_device','CPU')})
    while not (session/'stop.flag').exists():
        inbox=session/'request.json'
        if not inbox.exists():
            time.sleep(.12); continue
        processing=session/'processing.json'
        try:
            inbox.replace(processing)
        except FileNotFoundError:
            continue
        request={}
        try:
            request=json.loads(processing.read_text(encoding='utf-8'))
            rid=request['id']; mode=request['mode']; values=validate_settings(request['settings'])
            studio.atomic_json(status,{'state':'rendering','id':rid,'mode':mode,'device':scene.get('pipe_device','CPU')})
            if mode=='preview':
                values.update(resolution=960,samples=20)
                studio.apply_settings(scene,values)
                folder=session/'preview'; folder.mkdir(exist_ok=True)
                info=studio.export_frame(scene,folder,'preview_'+rid)
                studio.atomic_json(status,{'state':'done','id':rid,'mode':mode,'image':str(folder/info['image']),
                                          'mask':str(folder/info['mask']),'metadata':info,'device':scene.get('pipe_device','CPU')})
                # Bound the active session's generated preview cache.
                for sub,suffix in [('images','.png'),('masks','.png'),('labels','.txt'),('metadata','.json')]:
                    files=sorted((folder/sub).glob('preview_*'+suffix),key=lambda p:p.stat().st_mtime,reverse=True)
                    for old in files[3:]:
                        old.unlink(missing_ok=True)
            elif mode=='export':
                folder=Path(request['folder']).resolve()
                # Only the application-created destination is accepted for a render job.
                if not folder.is_dir() or not (folder/'job.json').is_file():
                    raise ValueError('Export destination has no job recipe.')
                job=json.loads((folder/'job.json').read_text(encoding='utf-8'))
                if not isinstance(job.get('count'),int) or not 1<=job['count']<=1000:
                    raise ValueError('Export count must be between 1 and 1000.')
                job['settings']=values
                studio.atomic_json(folder/'job.json',job)
                studio.run_job(folder/'job.json')
                result=studio.read_status(folder)
                if result.get('state')=='failed':
                    raise RuntimeError(result.get('error','Render failed'))
                studio.atomic_json(status,{'state':'done','id':rid,'mode':mode,'folder':str(folder),
                                          'result':result,'device':scene.get('pipe_device','CPU')})
            else:
                raise ValueError('Unknown request type.')
        except Exception:
            error=traceback.format_exc()
            print(error,flush=True)
            studio.atomic_json(status,{'state':'error','id':request.get('id'),'error':error})
        finally:
            processing.unlink(missing_ok=True)
    studio.atomic_json(status,{'state':'stopped'})


if __name__=='__main__':
    args=sys.argv[sys.argv.index('--')+1:]
    run(args[0])
