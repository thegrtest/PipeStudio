"""Unattended rolling collection: bounded workers, retries and an exclusive lock."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def read(path):
    try:return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def write(path,data):
    path=Path(path);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    os.replace(temporary,path)


def acquire(folder):
    handle=(Path(folder)/'supervisor.lock').open('a+b')
    if handle.tell()==0:handle.write(b'0');handle.flush()
    handle.seek(0)
    try:
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError:handle.close();return None
    return handle


def is_active(folder):
    if not Path(folder).is_dir():return False
    handle=acquire(folder)
    if handle is None:return True
    handle.close();return False


def supervise(folder,blender,command_factory=None,backoffs=(5,15,30)):
    folder=Path(folder)
    lock=acquire(folder)
    if lock is None:print('Collection is already supervised.',flush=True);return 0
    job=read(folder/'job.json');attempts=0;failures=0;restarts=0
    try:
        while True:
            before=read(folder/'status.json')
            if before.get('state')=='complete':return 0
            attempts+=1
            log_path=folder/f'worker_{attempts:04d}_{time.time_ns()}.log'
            command=(command_factory(attempts) if command_factory else
                [blender,'--background',str(folder/'source.blend'),'--python-exit-code','1','--python',
                 str(Path(__file__).with_name('rolling_capture.py')),'--',str(folder/'job.json')])
            with log_path.open('w',encoding='utf-8') as log:
                process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,cwd=str(Path(__file__).parent),
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                write(folder/'supervisor.json',dict(pid=os.getpid(),worker_pid=process.pid,workers_started=attempts,
                    restarts=restarts,worker_log=log_path.name,state='running'))
                try:code=process.wait(timeout=job.get('worker_timeout_seconds',7200))
                except subprocess.TimeoutExpired:
                    process.kill();process.wait();code=-999
            after=read(folder/'status.json')
            state=after.get('state')
            if code==0 and state in ('complete','cancelled','exhausted'):
                write(folder/'supervisor.json',dict(pid=os.getpid(),workers_started=attempts,restarts=restarts,state=state))
                return 0 if state!='exhausted' else 2
            if code==0 and state=='checkpoint':failures=0;continue
            restarts+=1
            advanced=after.get('attempted',0)>before.get('attempted',0)
            failures=1 if advanced else failures+1
            if failures>=3 or restarts>=12:
                write(folder/'status.json',{**after,'state':'failed','error':after.get('error') or
                    f'Renderer exited with code {code}; automatic retry limit reached. Resume after resolving the worker error.',
                    'last_worker_log':log_path.name})
                write(folder/'supervisor.json',dict(pid=os.getpid(),workers_started=attempts,restarts=restarts,state='failed'))
                return 1
            write(folder/'status.json',{**after,'state':'recovering','last_exit_code':code,
                'last_worker_log':log_path.name,'automatic_restarts':restarts})
            time.sleep(backoffs[min(failures-1,len(backoffs)-1)])
    finally:lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('folder');parser.add_argument('--blender',required=True)
    args=parser.parse_args();sys.exit(supervise(args.folder,args.blender))
