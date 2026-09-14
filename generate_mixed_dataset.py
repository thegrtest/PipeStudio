"""Render and verify four 500-image folders; resumable, with a live progress file."""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from dataset_tools import validate_dataset
from mixed_dataset import write_dataset,validate_mixed_plan

ROOT=Path(__file__).resolve().parent
BLENDER=Path(r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe')

def atomic_json(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,allow_nan=False),encoding='utf-8')
    os.replace(temporary,path)

def read_json(path,default=None):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError: return default

@contextmanager
def generation_lock(root):
    """Prevent a second resume command from writing into an active run."""
    import ctypes
    from ctypes import wintypes
    import msvcrt
    progress=read_json(root/'progress.json',{}) or {}
    pid=progress.get('supervisor_pid')
    if pid and pid!=os.getpid() and progress.get('state') in ('rendering','validating'):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
        kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes=[wintypes.HANDLE,ctypes.POINTER(wintypes.DWORD)]
        kernel.CloseHandle.argtypes=[wintypes.HANDLE]
        handle=kernel.OpenProcess(0x1000,False,int(pid))
        if handle:
            try:
                code=wintypes.DWORD()
                if kernel.GetExitCodeProcess(handle,ctypes.byref(code)) and code.value==259:
                    raise RuntimeError('Generation is already running; follow progress.json instead of starting another copy.')
            finally: kernel.CloseHandle(handle)
    with (root/'.generation.lock').open('a+b') as lock:
        if lock.tell()==0: lock.write(b'0');lock.flush()
        lock.seek(0)
        try: msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        except OSError as exc: raise RuntimeError('Another generator holds this output folder.') from exc
        try: yield
        finally:
            lock.seek(0);msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)

def final_check(root,plans):
    request=read_json(root/'dataset_request.json');batches=[];digests=set();names=set();seeds=set()
    for path in plans:
        plan=validate_mixed_plan(read_json(path));folder=path.parent
        validation=validate_dataset(folder)
        if not validation['valid']: raise ValueError(validation['errors'])
        manifest=read_json(folder/'manifest.json');samples=manifest['samples']
        if len(samples)!=500: raise ValueError('Incomplete batch: '+str(folder))
        stems={s['sample_id'] for s in samples}
        for sub,suffix in (('images','.png'),('labels','.txt')):
            actual={p.stem for p in (folder/sub).iterdir() if p.is_file() and p.suffix==suffix}
            if actual!=stems: raise ValueError('Missing or extra image/label files: '+str(folder/sub))
        classes=Counter(s['defect_type'] for s in samples)
        environments=Counter(s['parameters']['environment'] for s in samples)
        if classes!=request['counts_per_batch'] or environments!=request['environments_per_batch']:
            raise ValueError('Rendered class/environment totals disagree with the request.')
        for item in samples:
            stem=item['sample_id'];seed=item['parameters']['seed']
            if stem in names or seed in seeds: raise ValueError('Repeated specimen identity across batches.')
            names.add(stem);seeds.add(seed)
            digest=hashlib.sha256((folder/item['image']).read_bytes()).hexdigest()
            if digest in digests: raise ValueError('Byte-identical image repeated across batches.')
            digests.add(digest)
            label=(folder/'labels'/(stem+'.txt')).read_text().strip()
            if item['defect_type']=='NONE':
                if label or item['bbox_xywh']: raise ValueError('Good image has a defect annotation.')
            else:
                lines=label.splitlines()
                expected={'FOLD':'0','DENT':'1'}[item['defect_type']]
                if len(lines)!=1 or lines[0].split()[0]!=expected or item['visible_mask_pixels']<8:
                    raise ValueError('Incorrect or missing visible defect label: '+stem)
        batches.append({'folder':str(folder.parent.relative_to(root)),'images':500,'labels':500,
                        'classes':dict(classes),'environments':dict(environments),
                        'severity':dict(Counter(s['severity'] for s in samples)),
                        'validation':validation})
    result={'state':'complete','completed_utc':datetime.now(timezone.utc).isoformat(),
            'images':2000,'labels':2000,'unique_image_hashes':len(digests),'unique_specimen_seeds':len(seeds),
            'classes':{k:v*4 for k,v in request['counts_per_batch'].items()},
            'environments':{'MACHINE':1000,'GODSLIGHT':1000},'batches':batches}
    atomic_json(root/'completion.json',result)
    rows=''.join(f'<tr><td><a href="{b["folder"]}/all/report/index.html">{b["folder"]}</a></td><td>500</td>'
                 f'<td>{b["classes"]["NONE"]}</td><td>{b["classes"]["FOLD"]}</td><td>{b["classes"]["DENT"]}</td>'
                 f'<td>250 / 250</td><td>{b["severity"].get("small",0)}</td></tr>' for b in batches)
    (root/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Brass synthetic 2000</title>'
        '<style>body{font:16px system-ui;background:#111c23;color:#e8e8df;margin:40px;line-height:1.6}a{color:#eed197}'
        'td,th{text-align:left;padding:12px 22px;border-bottom:1px solid #43525b}table{border-collapse:collapse}</style>'
        '<h1>2,000 tapered brass pipe images</h1><p>Four verified mixed folders. Open a batch to inspect images and defect boxes.</p>'
        '<table><tr><th>Folder</th><th>Images</th><th>Good</th><th>Fold</th><th>Dent</th><th>Upright / GodsLight</th><th>Small defects</th></tr>'
        +rows+'</table><p>Each batch uses all/images and all/labels. YOLO: 0 Fold, 1 Dent; good images have empty labels.</p>'
        '<p><a href="completion.json">Verification details</a> · <a href="README.md">Dataset notes</a></p></html>',encoding='utf-8')
    return result

def run(root,plans,workers=4,threads=8,resume=False):
    if not BLENDER.is_file(): raise FileNotFoundError(BLENDER)
    started=time.monotonic();running={};pending=[];logs=[];failed=[];last_report=0
    initial=sum((read_json(p.parent/'status.json',{}) or {}).get('completed',0) for p in plans)
    cancel=root/'cancel.flag'
    if resume and cancel.exists(): cancel.unlink()
    for path in plans:
        state=read_json(path.parent/'status.json',{})
        if state.get('state')!='complete': pending.append(path)
    try:
        while pending or running:
            cancelled=cancel.exists()
            if cancelled:
                for path in running: (path.parent/'cancel.flag').touch()
                pending.clear()
            while pending and len(running)<workers and not cancelled and not failed:
                path=pending.pop(0);log=(path.parent/'render.log').open('a',encoding='utf-8');logs.append(log)
                command=[str(BLENDER),'-b','--factory-startup','-t',str(threads),'--python-exit-code','1',
                         '--python',str(ROOT/'pipeline_runner.py'),'--','--plan',str(path)]
                if (path.parent/'manifest.json').exists(): command+=['--resume']
                process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                running[path]=process
            for path,process in list(running.items()):
                code=process.poll()
                if code is not None:
                    del running[path]
                    state=read_json(path.parent/'status.json',{})
                    if code or state.get('state') not in ('complete','cancelled'):
                        failed.append({'batch':str(path.parent.parent.relative_to(root)),'exit_code':code,
                                       'error':state.get('error','See render.log')})
            states=[{'folder':str(p.parent.parent.relative_to(root)),**(read_json(p.parent/'status.json',{}) or {})} for p in plans]
            completed=sum(s.get('completed',0) for s in states)
            elapsed=time.monotonic()-started;new=completed-initial
            remaining=(2000-completed)*elapsed/new if new>0 else None
            status='failed' if failed else 'cancelled' if cancelled else 'rendering'
            atomic_json(root/'progress.json',{'state':status,'completed':completed,'total':2000,
                'elapsed_seconds':round(elapsed),'estimated_remaining_seconds':round(remaining) if remaining else None,
                'active_worker_pids':[p.pid for p in running.values()],'supervisor_pid':os.getpid(),
                'updated_utc':datetime.now(timezone.utc).isoformat(),'batches':states,'failures':failed})
            if time.monotonic()-last_report>=30 or not running:
                print(f'MIXED_PROGRESS {completed}/2000; {len(running)} workers; estimated remaining {round(remaining/60) if remaining else "?"} min',flush=True)
                last_report=time.monotonic()
            if failed:
                # Other workers finish their current image and retain valid prefixes.
                for path in running: (path.parent/'cancel.flag').touch()
                pending.clear()
            if running or pending: time.sleep(5)
        if failed: raise RuntimeError('A batch failed; inspect progress.json and its render.log, then resume.')
        if cancel.exists(): return {'state':'cancelled'}
        progress=read_json(root/'progress.json',{});progress['state']='validating';atomic_json(root/'progress.json',progress)
        result=final_check(root,plans)
        progress.update(state='complete',completed=2000,estimated_remaining_seconds=0,active_worker_pids=[],
                        elapsed_seconds=round(time.monotonic()-started))
        atomic_json(root/'progress.json',progress)
        print('MIXED_DATASET_COMPLETE '+str(root),flush=True)
        return result
    except BaseException as exc:
        # A stopped supervisor asks workers to exit safely after their current image.
        for path in running: (path.parent/'cancel.flag').touch()
        progress=read_json(root/'progress.json',{}) or {}
        progress.update(state='failed',supervisor_error=str(exc));atomic_json(root/'progress.json',progress)
        raise
    finally:
        for log in logs: log.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--good',type=int,default=50,help='Good images per 500-image folder')
    parser.add_argument('--fold',type=int,default=225,help='Fold images per folder')
    parser.add_argument('--dent',type=int,default=225,help='Dent images per folder')
    parser.add_argument('--seed',type=int,default=20260911)
    parser.add_argument('--workers',type=int,choices=(1,2,3,4),default=4)
    parser.add_argument('--threads',type=int,default=8)
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--verify-only',action='store_true')
    args=parser.parse_args();root=args.output.resolve()
    if args.resume or args.verify_only:
        request=read_json(root/'dataset_request.json')
        if not request: raise ValueError('No saved dataset request in '+str(root))
        plans=[(root/p).resolve() for p in request['plans']]
        if any(not p.is_relative_to(root) for p in plans): raise ValueError('Plan outside the dataset folder.')
    else:
        plans=write_dataset(root,{'NONE':args.good,'FOLD':args.fold,'DENT':args.dent},args.seed)
    if args.prepare_only:
        print('MIXED_DATASET_PREPARED '+str(root));return
    with generation_lock(root):
        result=final_check(root,plans) if args.verify_only else run(root,plans,args.workers,args.threads,args.resume)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__': main()
