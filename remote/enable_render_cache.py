"""Apply a verified RGB-only cache policy without changing the saved specimens."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import time
from datetime import datetime

from fleet import (ROOT, bootstrap, node_call, parallel, runtime_config, source_manifest,
                   failed_results)
from fleet_common import digest_file, digest_json, read_json, write_json
from fleet_node import lock
from roll_fleet_update import staged_update


def cache_snapshot(settings):
    archive=Path(settings['archive'])
    if digest_file(archive)!=settings['archive_sha256']:
        raise ValueError('Original source archive checksum differs')
    with tarfile.open(archive) as package:
        manifest=json.load(package.extractfile('release.json'))['files']
        contents={name:package.extractfile(name).read() for name in manifest}
    if any(hashlib.sha256(data).hexdigest()!=manifest[name] for name,data in contents.items()):
        raise ValueError('Original release contents differ')
    contents['fast_pipeline.py']=(ROOT/'fast_pipeline.py').read_bytes()
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
    release=digest_json(manifest)
    target=ROOT/'.cache/fleet-packages'/(release+'.tgz')
    if not target.exists():
        contents['release.json']=json.dumps(dict(files=manifest,release=release),indent=2).encode()
        temporary=target.with_suffix('.cache.tmp')
        with tarfile.open(temporary,'w:gz',compresslevel=1) as package:
            for name,data in contents.items():
                info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o644
                package.addfile(info,io.BytesIO(data))
        os.replace(temporary,target)
    return release,target,digest_file(target)


def verify_trial(path, source_release):
    report=read_json(path)
    if report['release']!=source_release:
        raise ValueError('Trial used a different production release')
    if (report.get('candidate') not in ('beauty_only','production') or report['samples']<4
            or report['samples']!=len(report['samples_detail'])):
        raise ValueError('Expected a complete RGB-only cache comparison of at least four specimens')
    if not all(report[key] for key in ('all_labels_exact','all_masks_exact','all_metadata_exact')):
        raise ValueError('Cache trial changed labels, masks, or capture settings')
    # GPU renders vary slightly even in uncached repeats; bound the RGB change
    # far below one average 8-bit level while requiring exact annotations.
    if any(r['mean_abs_rgb_difference']>.001 or r['max_rgb_difference']>4
           for r in report['samples_detail']):
        raise ValueError('RGB changes exceed the matched-render tolerance')
    if report['time_saved_percent']<=0:
        raise ValueError('Caching did not improve this device in its benchmark')
    return report


def enable(parent, trials, production_trial):
    settings=read_json(parent/'fleet.json')
    evidence={name:verify_trial(path,settings['release']) for name,path in trials.items()}
    nodes=json.loads(json.dumps(settings['nodes']))
    if not evidence or not set(evidence).issubset(nodes):
        raise ValueError('Select tested fleet devices')
    for name in evidence:
        nodes[name].setdefault('env',{})['PIPESTUDIO_RENDER_CACHE']='beauty'
    saved=cache_snapshot(settings)
    production_evidence=verify_trial(production_trial,saved[0])
    stages=parallel(nodes,lambda name,node:staged_update(node,saved))
    print(json.dumps(dict(staged=stages)),flush=True)
    if failed_results(stages): raise RuntimeError('Staging failed; production was not stopped')
    job=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_cache'
    folder=ROOT/'exports/fleet_runs'/job;folder.mkdir()
    write_json(folder/'cache-request.json',dict(parent=str(parent),trials={k:str(v) for k,v in trials.items()},
        release=saved[0],evidence=evidence,production_trial=str(production_trial),
        production_evidence=production_evidence))
    receipts={};started={};paused=[]
    for name,node in nodes.items():
        state=node_call(node,dict(action='status'))
        if state['job']!=settings['job']: raise ValueError('Active job changed on '+name)
        was_running=state['running'];was_complete=state['state']=='complete'
        if was_running:
            node_call(node,dict(action='stop',job=settings['job']))
            deadline=time.monotonic()+900
            while state['running']:
                if time.monotonic()>deadline: raise TimeoutError('Image boundary timeout: '+name)
                time.sleep(2)
                state=node_call(node,dict(action='status'))
        keep_paused=not was_running and not was_complete
        if keep_paused: paused.append(name)
        try:
            bootstrap(node)
            plan=read_json(parent/(name+'.plan.json'))
            write_json(folder/(name+'.plan.json'),plan)
            config={**runtime_config(node),'release':saved[0]}
            receipts[name]=node_call(node,dict(action='continue_release',job=job,parent_job=settings['job'],
                completed=state['completed'],plan=plan,config=config,paused=keep_paused))
            node_call(node,dict(action='stage_release',release=saved[0],files=source_manifest(saved[1])))
            if not keep_paused:
                started[name]=node_call(node,dict(action='start',job=job))
            write_json(folder/'cache-progress.json',dict(deployed=receipts,started=started))
            print(json.dumps(dict(device=name,cache=node.get('env',{}).get('PIPESTUDIO_RENDER_CACHE','off'),
                                  paused=keep_paused,**receipts[name])),flush=True)
        except Exception:
            if was_running:
                current=node_call(node,dict(action='status'))
                if not current['running']: node_call(node,dict(action='resume',job=settings['job']))
            raise
    plan=read_json(parent/'render_plan.json');write_json(folder/'render_plan.json',plan)
    write_json(folder/'fleet.json',{**settings,'job':job,'release':saved[0],'archive':str(saved[1]),
        'archive_sha256':saved[2],'nodes':nodes,'continued_from':str(parent),'paused_nodes':paused})
    write_json(folder/'deployment.json',receipts);write_json(folder/'start-result.json',started)
    write_json(ROOT/'.cache/fleet-active.json',dict(folder=str(folder)))
    write_json(parent/'continued_to.json',dict(folder=str(folder),reason='Verified RGB cache; fresh label masks'))
    local=read_json(ROOT/'fleet_nodes.local.json')
    for name in evidence:
        local['nodes'][name].setdefault('env',{})['PIPESTUDIO_RENDER_CACHE']='beauty'
    write_json(ROOT/'fleet_nodes.local.json',local)
    print(json.dumps(dict(run=str(folder),cache_devices=list(evidence),paused=paused),indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--trial',action='append',required=True,help='node=local comparison JSON')
    parser.add_argument('--production-trial',type=Path,required=True)
    args=parser.parse_args()
    parent=args.run or Path(read_json(ROOT/'.cache/fleet-active.json')['folder'])
    trials={name:Path(path) for name,path in (value.split('=',1) for value in args.trial)}
    with lock(ROOT/'.cache/fleet-controller.lock'): enable(parent,trials,args.production_trial)
