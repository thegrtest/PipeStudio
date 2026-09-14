"""One command from ordinary Python: plan, render, validate, and open the gallery."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import uuid
from generation_plan import make_plan,write_plan

ROOT=Path(__file__).resolve().parent
BLENDER=Path(r'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--seed',type=int,default=42)
    parser.add_argument('--specimens',type=int,default=8)
    parser.add_argument('--quality',choices=('quick','full'),default='quick')
    parser.add_argument('--environment',choices=('BOTH','MACHINE','GODSLIGHT'),default='BOTH')
    parser.add_argument('--resume',type=Path,metavar='PLAN_JSON')
    parser.add_argument('--no-open',action='store_true')
    args=parser.parse_args()
    if not BLENDER.is_file(): raise FileNotFoundError('Blender executable not found: '+str(BLENDER))
    if args.resume:
        path=args.resume.resolve()
    else:
        folder=args.output or ROOT/'exports'/('test_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:5])
        envs=('MACHINE','GODSLIGHT') if args.environment=='BOTH' else (args.environment,)
        path=write_plan(make_plan(args.seed,args.specimens,envs,args.quality),folder)
    command=[str(BLENDER),'-b','--factory-startup','--python-exit-code','1','--python',str(ROOT/'pipeline_runner.py'),
             '--','--plan',str(path)]+(['--resume'] if args.resume else [])
    print('Rendering test set. Progress and errors: '+str(path.parent/'render.log'),flush=True)
    with (path.parent/'render.log').open('a',encoding='utf-8') as log:
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if result.returncode:
        print('Renderer failed. See '+str(path.parent/'render.log')); return result.returncode
    import json
    status=json.loads((path.parent/'status.json').read_text(encoding='utf-8'))
    print(status['state']+': '+str(path.parent))
    if status['state']=='complete' and not args.no_open:
        os.startfile(str(path.parent/'report'/'index.html'))
    return 0

if __name__=='__main__': raise SystemExit(main())
