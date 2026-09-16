"""GPU-only production worker with bounded retries for Windows file locks."""
import argparse
import json
import os
from pathlib import Path
import sys
import time
import tempfile
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))


def atomic_json(path,data):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    payload=json.dumps(data,indent=2,allow_nan=False)
    for attempt in range(12):
        try:
            temporary.write_text(payload,encoding='utf-8');os.replace(temporary,path);return
        except PermissionError:
            if attempt==11: raise
            time.sleep(min(.025*2**attempt,.8))


def install(studio):
    if getattr(studio,'_fast_worker_installed',False): return
    cache_mode=os.environ.get('PIPESTUDIO_RENDER_CACHE','off').lower()
    if cache_mode not in ('off','beauty'):
        raise ValueError('PIPESTUDIO_RENDER_CACHE must be off or beauty')
    configure=studio.configure_renderer
    def gpu_config(scene):
        configure(scene)
        if scene.cycles.device!='GPU' or scene.get('pipe_device')=='CPU':
            raise RuntimeError('GPU rendering unavailable. Refusing a slow silent CPU fallback.')
        # Explicitly keep denoising on the GPU when supported by this build.
        if hasattr(scene.cycles,'denoising_use_gpu'): scene.cycles.denoising_use_gpu=True
        scene.render.compositor_device='GPU'
        scene.render.compositor_precision='FULL'
        # Cached low-sample mask passes can shift support edges and YOLO boxes.
        # Reuse data for RGB only; every annotation pass gets a fresh session.
        scene.render.use_persistent_data=cache_mode=='beauty'
        scene['pipe_render_cache']=cache_mode
        print('FAST_GPU '+str(scene.get('pipe_device'))+' / '+scene.cycles.denoiser,flush=True)
        print('RENDER_CACHE '+cache_mode,flush=True)
    if cache_mode=='beauty':
        mask_mode=studio.set_mask_mode
        def fresh_mask_mode(scene,active):
            scene.render.use_persistent_data=not active
            return mask_mode(scene,active)
        studio.set_mask_mode=fresh_mask_mode
    original_export=studio.export_frame
    def export(scene,folder,stem):
        # Finish both PNG writes outside OneDrive, then publish each completed file.
        # The source exporter writes beauty/mask twice; staging avoids syncing intermediates.
        scratch=Path(tempfile.gettempdir())/'PipeStudioFast'/('worker_'+str(os.getpid()))
        scratch.mkdir(parents=True,exist_ok=True)
        info=original_export(scene,scratch,stem)
        if scene.pipe_studio.defect!='NONE' and info['visible_mask_pixels']<8:
            # A stale render cache can occasionally return an empty support pass.
            # Rebuild and retry the same recipe; the caller still rejects invisibility.
            persistent=scene.render.use_persistent_data
            try:
                scene.render.use_persistent_data=False
                studio.refresh(scene,geometry=True)
                info=original_export(scene,scratch,stem)
                info['render_cache_retry']=True
            finally: scene.render.use_persistent_data=persistent
        for relative in (info['image'],info['mask'],'labels/'+stem+'.txt','metadata/'+stem+'.json'):
            source=scratch/relative;target=Path(folder)/relative;target.parent.mkdir(parents=True,exist_ok=True)
            for attempt in range(12):
                try: os.replace(source,target);break
                except PermissionError:
                    if attempt==11: raise
                    time.sleep(min(.025*2**attempt,.8))
                except OSError as exc:
                    if exc.errno!=18 and getattr(exc,'winerror',None)!=17: raise
                    import shutil
                    shutil.copy2(source,target);source.unlink();break
        return info
    studio.configure_renderer=gpu_config;studio.atomic_json=atomic_json;studio.export_frame=export
    studio._fast_worker_installed=True


def main():
    import pipeline_runner as runner
    install(runner.studio)
    runner.CODE_FILES=runner.CODE_FILES+('fast_pipeline.py',)
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--plan',required=True)
    ap.add_argument('--resume',action='store_true')
    args=ap.parse_args(sys.argv[sys.argv.index('--')+1:])
    runner.run(args.plan,args.resume)


if __name__=='__main__': main()
