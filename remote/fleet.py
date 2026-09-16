"""Dispatch a saved camera-matched generation plan across desktop and SSH nodes."""
import argparse
from copy import deepcopy
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import secrets
import shutil
import subprocess
import sys
import tarfile
import time
import uuid
from datetime import datetime
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fleet_common import allocate, digest_file, digest_json, inside, read_json, safe_name, split_plan, write_json


def run(command, **kwargs):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-5000:] or result.stdout.decode(errors='replace')[-5000:])
    return result.stdout


def node_call(node, request):
    agent = str(Path(node['root'])/'bin/fleet_node.py').replace('\\','/')
    arguments = [node['python'], agent, '--root', node['root']]
    command = arguments if node['transport']=='local' else ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',node['alias'],shlex.join(arguments)]
    timeout = 1800 if request['action']=='pack' else 300 if request['action'] in ('continue_defects','continue_release') else 180 if request['action'] in ('install','install_patch') else 30
    result = json.loads(run(command,input=json.dumps(request).encode(),timeout=timeout))
    if result.get('error') and 'state' not in result: raise RuntimeError(result['error'])
    return result


def copy_to(node, source, relative):
    target = str(Path(node['root'])/relative).replace('\\','/')
    if node['transport']=='local':
        Path(target).parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
    else:
        run(['scp','-q','-o','BatchMode=yes',str(source),node['alias']+':'+target])


def bootstrap(node):
    names=('fleet_common.py','release_store.py','fleet_node.py')
    probe="""import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
for name in ('bin','incoming'): (root/name).mkdir(parents=True,exist_ok=True)
print(json.dumps({n:hashlib.sha256((root/'bin'/n).read_bytes()).hexdigest() if (root/'bin'/n).is_file() else None for n in json.load(sys.stdin)}))
"""
    if node['transport']=='local':
        command=[node['python'],'-c',probe,node['root']]
    else:
        command=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',node['alias'],shlex.join([node['python'],'-c',probe,node['root']])]
    hashes=json.loads(run(command,input=json.dumps(names).encode(),timeout=30))
    changed=[n for n in names if digest_file(ROOT/'remote'/n)!=hashes[n]]
    if changed and hashes.get('fleet_node.py') and node_call(node,dict(action='status'))['running']:
        raise RuntimeError('Node is generating; worker updates are deferred until idle')
    for name in changed:
        relative='incoming/'+name+'.'+digest_file(ROOT/'remote'/name)+'.tmp'
        copy_to(node,ROOT/'remote'/name,relative)
        source=str(Path(node['root'])/relative).replace('\\','/')
        target=str(Path(node['root'])/'bin'/name).replace('\\','/')
        if node['transport']=='local': os.replace(source,target)
        else: run(['ssh','-o','BatchMode=yes',node['alias'],shlex.join([node['python'],'-c','import os,sys; os.replace(sys.argv[1],sys.argv[2])',source,target])],timeout=30)
    return changed


def snapshot():
    from generate_domain_dataset import CODE_FILES
    paths = [p for p in ROOT.glob('*.py') if not p.name.startswith('test_')]
    # The renderer owns this dependency list; it may include newly added JSON
    # calibration data as well as Python modules.
    paths += [inside(ROOT,name) for name in CODE_FILES]
    paths += list((ROOT/'remote').glob('blender_*.sh'))
    paths += list((ROOT/'flashlight_lab').glob('*.py'))+list((ROOT/'flashlight_lab/assets').glob('*.png'))
    paths += [p for p in (ROOT/'references').glob('*') if p.suffix.lower() in ('.png','.jpg','.jpeg')]
    contents = {p.relative_to(ROOT).as_posix():p.read_bytes() for p in sorted(set(paths))}
    if any(digest_file(ROOT/name)!=hashlib.sha256(data).hexdigest() for name,data in contents.items()):
        raise RuntimeError('Renderer files changed during packaging; retry when the edit is saved')
    manifest = {name:hashlib.sha256(data).hexdigest() for name,data in contents.items()}
    release = digest_json(manifest)
    folder = ROOT/'.cache/fleet-packages'; folder.mkdir(parents=True,exist_ok=True)
    archive = folder/(release+'.tgz')
    if not archive.exists():
        contents['release.json'] = json.dumps(dict(files=manifest,release=release),indent=2).encode()
        temporary = archive.with_suffix('.tmp')
        with tarfile.open(temporary,'w:gz',compresslevel=1) as package:
            for name,data in contents.items():
                info = tarfile.TarInfo(name); info.size=len(data); info.mode=0o644
                package.addfile(info,io.BytesIO(data))
        os.replace(temporary,archive)
    return release,archive,digest_file(archive)


def planned_work(args, nodes):
    from domain_plan import make_plan, validate_domain_plan, defects_only_plan
    def make(seed):
        plan=make_plan(args.count,seed,args.quality,args.smoke,profile=getattr(args,'profile','reference'))
        return defects_only_plan(plan) if getattr(args,'defects_only',False) and not args.smoke else plan
    plan = make(args.seed)
    if getattr(args,'per_node',False) and not args.smoke:
        if args.seed+args.count*len(nodes)>2000000000:
            raise ValueError('Seed range must accommodate every device without overlap')
        rows=[]; assignment={}
        for offset,name in enumerate(nodes):
            shard=plan if offset==0 else make(args.seed+offset*args.count)
            assignment[name]=list(range(len(rows),len(rows)+len(shard['samples'])))
            rows.extend(shard['samples'])
        plan['samples']=rows
        plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in rows))
        plan['expected_instance_counts']=dict(Counter(a['kind'] for r in rows for a in r['instances']))
        plan['expected_setup_counts']=dict(Counter(r['setup'] for r in rows))
        validate_domain_plan(plan)
        return plan,assignment
    if args.smoke:
        selected=[]
        kinds=('NONE','FOLD','DENT','SOAP_STAIN','OIL_STAIN') if getattr(args,'verification',False) else ('NONE','FOLD','DENT')
        if getattr(args,'defects_only',False): kinds=tuple(k for k in kinds if k!='NONE')
        for kind in kinds:
            for offset in range(len(nodes)):
                selected.append([r for r in plan['samples'] if r['primary_kind']==kind][offset])
        plan['samples']=selected
        plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in selected))
        plan['expected_instance_counts']=dict(Counter(a['kind'] for r in selected for a in r['instances']))
        plan['expected_setup_counts']=dict(Counter(r['setup'] for r in selected))
        validate_domain_plan(plan)
    assignment = allocate(len(plan['samples']), {name:{**node,'weight':1} if args.smoke else node for name,node in nodes.items()})
    return plan,assignment


def prepare(args, nodes, saved_snapshot=None):
    plan,assignment=planned_work(args,nodes)
    shards = split_plan(plan,assignment)
    release,archive,archive_hash = saved_snapshot or snapshot()
    job = datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+release[:8]
    folder=ROOT/'exports/fleet_runs'/job; folder.mkdir(parents=True,exist_ok=False)
    write_json(folder/'render_plan.json',plan)
    write_json(folder/'fleet.json',dict(job=job,release=release,archive=str(archive),archive_sha256=archive_hash,
        nodes=nodes,assignments=assignment,source_plan_sha256=digest_json(plan),smoke=args.smoke,
        count_per_node=args.count if getattr(args,'per_node',False) and not args.smoke else None))
    for name,shard in shards.items(): write_json(folder/(name+'.plan.json'),shard)
    write_json(ROOT/'.cache/fleet-active.json',dict(folder=str(folder)))
    return folder


def source_manifest(archive):
    with tarfile.open(archive) as package:
        return json.load(package.extractfile('release.json'))['files']


def patch_archive(archive, release, missing):
    folder=ROOT/'.cache/fleet-packages/deltas'; folder.mkdir(parents=True,exist_ok=True)
    key=digest_json(dict(release=release,missing=sorted(missing)))
    target=folder/(key+'.tgz')
    if not target.exists():
        temporary=target.with_suffix('.'+uuid.uuid4().hex+'.tmp')
        with tarfile.open(archive) as original, tarfile.open(temporary,'w:gz',compresslevel=1) as patch:
            for name in sorted(missing):
                member=original.getmember(name)
                patch.addfile(member,original.extractfile(member))
        os.replace(temporary,target)
    return target


def sync_one(node, saved_snapshot):
    release,archive,archive_hash=saved_snapshot
    if digest_file(archive)!=archive_hash: raise ValueError('Saved source archive changed')
    agent_files=bootstrap(node)
    files=source_manifest(archive)
    request=dict(release=release,files=files)
    offer=node_call(node,dict(action='stage_release',**request))
    if offer['installed']:
        return dict(release=release,changed=0,reused=len(files),bytes_sent=0,agent_files=agent_files)
    patch=patch_archive(archive,release,offer['missing'])
    copy_to(node,patch,'incoming/'+patch.name)
    result=node_call(node,dict(action='install_patch',archive=patch.name,sha256=digest_file(patch),
        base_release=offer['base_release'],**request))
    return dict(release=release,changed=result['changed'],reused=result['reused'],
                bytes_sent=patch.stat().st_size,agent_files=agent_files)


def runtime_config(node):
    return {key:node[key] for key in ('blender','env','threads','chunk','seconds_per_image') if key in node}


def parallel(nodes, function):
    with ThreadPoolExecutor(max_workers=len(nodes)) as pool:
        futures={name:pool.submit(function,name,node) for name,node in nodes.items()}
        results={}
        for name,future in futures.items():
            try: results[name]=future.result()
            except Exception as error: results[name]=dict(error=str(error))
    return results


def deploy(folder, settings):
    def one(name,node):
        update=sync_one(node,(settings['release'],Path(settings['archive']),settings['archive_sha256']))
        config=runtime_config(node)
        config['release']=settings['release']
        prepared=node_call(node,dict(action='prepare',job=settings['job'],plan=read_json(folder/(name+'.plan.json')),config=config))
        return {**prepared,'update':update}
    results=parallel(settings['nodes'],one)
    write_json(folder/'deployment.json',results)
    if any('error' in value for value in results.values()):
        raise RuntimeError('No rendering started; deployment needs attention: '+json.dumps(results))
    return results


def fetch(folder, settings):
    def one(name,node):
        package=node_call(node,dict(action='pack',job=settings['job']))
        cache=folder/'transfers'; cache.mkdir(exist_ok=True)
        archive=cache/(name+'.tar.gz')
        if node['transport']=='local': shutil.copyfile(package['archive'],archive)
        else: run(['scp','-q','-o','BatchMode=yes',node['alias']+':'+package['archive'],str(archive)])
        if digest_file(archive)!=package['sha256']: raise ValueError('Returned dataset hash mismatch')
        dest=folder/'nodes'/name; dest.mkdir(parents=True,exist_ok=True)
        with tarfile.open(archive) as data:
            for member in data:
                if not (member.isfile() or member.isdir()): raise ValueError('Unexpected archive link')
                inside(dest,member.name)
                data.extract(member,dest,filter='data')
        return dict(folder=str(dest/settings['job']))
    results=parallel(settings['nodes'],one)
    write_json(folder/'retrieval.json',results)
    if any('error' in value for value in results.values()): return results
    output=folder/'dataset'; all_dir=output/'all'; all_dir.mkdir(parents=True,exist_ok=True)
    plan=read_json(folder/'render_plan.json'); write_json(output/'render_plan.json',plan)
    records={}; provenance={}
    for name,receipt in results.items():
        source=Path(receipt['folder'])/'all'; manifest=read_json(source/'manifest.json')
        provenance[name]={k:manifest.get(k) for k in ('blender_runtime','renderer_sources','source_segments','plan_sha256')}
        for record in manifest['samples']:
            sid=record['sample_id']
            if sid in records: raise ValueError('Duplicate specimen returned by multiple nodes: '+sid)
            records[sid]=record
            for rel,expected in record['output_sha256'].items():
                source_file=inside(source,rel); target=inside(all_dir,rel)
                if digest_file(source_file)!=expected: raise ValueError('Returned image/label/mask hash mismatch')
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():
                    try: os.link(source_file,target)
                    except OSError: shutil.copyfile(source_file,target)
                if digest_file(target)!=expected: raise ValueError('Existing collected file differs from source')
    planned=[r['sample_id'] for r in plan['samples']]
    if set(records)-set(planned): raise ValueError('Node returned an unassigned specimen')
    merged=dict(classes=plan['classes'],samples=[records[sid] for sid in planned if sid in records],
                plan_sha256=digest_json(plan),fleet_nodes=provenance)
    write_json(all_dir/'manifest.json',merged)
    (all_dir/'classes.txt').write_text('\n'.join(plan['classes'].values())+'\n')
    (all_dir/'data.yaml').write_text('path: '+all_dir.as_posix()+'\ntrain: images\nnames:\n'+''.join(f'  {k}: {json.dumps(v)}\n' for k,v in plan['classes'].items()))
    # Validate with the exact review code shipped for this run, even if the
    # working environment has since been edited.
    source_archive = Path(settings['archive'])
    if digest_file(source_archive) != settings['archive_sha256']:
        raise ValueError('Saved renderer archive changed')
    review_folder = folder/'review_source'; review_folder.mkdir(exist_ok=True)
    with tarfile.open(source_archive) as package:
        review_names=['domain_review.py','release.json']
        if 'glare_guard.py' in package.getnames(): review_names.append('glare_guard.py')
        for name in review_names:
            member = package.getmember(name)
            if not member.isfile(): raise ValueError('Invalid review source')
            (review_folder/name).write_bytes(package.extractfile(member).read())
    review_hashes = read_json(review_folder/'release.json')['files']
    for name in review_names:
        if name!='release.json' and digest_file(review_folder/name)!=review_hashes[name]:
            raise ValueError('Review source does not match this run: '+name)
    command=[sys.executable,str(review_folder/'domain_review.py'),str(output)]
    if len(records)!=len(planned): command.append('--allow-incomplete')
    validation=run(command)
    return dict(folder=str(output),images=len(records),planned=len(planned),validation=validation.decode()[-1500:])


def failed_results(results):
    return any('error' in value for value in results.values())


def continue_defects(folder, settings):
    """Resume with a new saved plan, carrying all verified committed outputs."""
    from domain_plan import defects_only_plan, validate_domain_plan
    nodes=settings['nodes']
    stopped=parallel(nodes,lambda name,node:node_call(node,dict(action='stop',job=settings['job'])))
    if failed_results(stopped): raise RuntimeError('Could not pause every node: '+json.dumps(stopped))
    deadline=time.monotonic()+900
    while True:
        states=parallel(nodes,lambda name,node:node_call(node,dict(action='status',job=settings['job'])))
        if failed_results(states): raise RuntimeError('Cannot read paused workers: '+json.dumps(states))
        if all(not s['running'] for s in states.values()): break
        if time.monotonic()>deadline: raise RuntimeError('Waiting for current images to finish; stop flags remain set')
        time.sleep(5)
    bootstrapped=parallel(nodes,lambda name,node:dict(changed=bootstrap(node)))
    if failed_results(bootstrapped): raise RuntimeError('Worker update failed: '+json.dumps(bootstrapped))
    plan=read_json(folder/'render_plan.json')
    if digest_json(plan)!=settings['source_plan_sha256']: raise ValueError('Saved parent plan changed')
    plan=deepcopy(plan); preserved=[]
    for name in nodes:
        shard=defects_only_plan(read_json(folder/(name+'.plan.json')),states[name]['completed'])
        preserved.extend(shard['generation_policy']['preserved_sample_ids'])
        for index,row in zip(settings['assignments'][name],shard['samples']): plan['samples'][index]=row
    plan['generation_policy']=dict(defects_only=True,preserved_sample_ids=preserved)
    plan['ratio_definition']='Remaining specimens all contain labeled defects; completed specimens are preserved.'
    plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in plan['samples']))
    plan['expected_instance_counts']=dict(Counter(a['kind'] for r in plan['samples'] for a in r['instances']))
    validate_domain_plan(plan)
    shards=split_plan(plan,settings['assignments'])
    job=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_defects'
    target=ROOT/'exports/fleet_runs'/job; target.mkdir(parents=True)
    continued={**settings,'job':job,'source_plan_sha256':digest_json(plan),'continued_from':str(folder),'defects_only':True}
    write_json(target/'render_plan.json',plan); write_json(target/'fleet.json',continued)
    for name,shard in shards.items(): write_json(target/(name+'.plan.json'),shard)
    def carry(name,node):
        return node_call(node,dict(action='continue_defects',job=job,parent_job=settings['job'],
            completed=states[name]['completed'],plan=shards[name],config={**runtime_config(node),'release':settings['release']}))
    deployed=parallel(nodes,carry); write_json(target/'deployment.json',deployed)
    if failed_results(deployed): raise RuntimeError('No generation restarted; continuation needs attention: '+json.dumps(deployed))
    write_json(ROOT/'.cache/fleet-active.json',dict(folder=str(target)))
    write_json(folder/'continued_to.json',dict(folder=str(target),reason='Future images must contain labeled defects'))
    started=parallel(nodes,lambda name,node:node_call(node,dict(action='start',job=job)))
    write_json(target/'start-result.json',started)
    if failed_results(started): raise RuntimeError('Continuation launch needs attention: '+json.dumps(started))
    return dict(run=str(target),preserved=len(preserved),remaining_defects=len(plan['samples'])-len(preserved),nodes=deployed,started=started)


def ready(args, nodes):
    """Update, verify once per version, and stage production without launching it."""
    if any(not node.get('ready') for node in nodes.values()):
        raise RuntimeError('Every selected device must first pass GPU preflight')
    saved=snapshot(); release=saved[0]
    updates=parallel(nodes,lambda name,node:sync_one(node,saved))
    print(json.dumps({'updates':updates}),flush=True)
    if failed_results(updates): raise RuntimeError('Update failed; no generation started')
    states=parallel(nodes,lambda name,node:node_call(node,dict(action='status')))
    if failed_results(states) and any('state' not in value for value in states.values() if 'error' in value):
        raise RuntimeError('Cannot verify all devices: '+json.dumps(states))
    checked=all(
        state.get('readiness',{}).get('release')==release and
        state.get('readiness',{}).get('runtime_signature')==digest_json(runtime_config(nodes[name])) and
        state.get('readiness',{}).get('quality')==args.quality and
        state.get('readiness',{}).get('images',0)>=(4 if args.defects_only else 5) and
        (args.defects_only or not state.get('readiness',{}).get('defects_only'))
        for name,state in states.items())
    previous_ready=read_json(ROOT/'.cache/fleet-ready.json',{})
    dataset=previous_ready.get('test_dataset') if previous_ready.get('release')==release else None
    if not checked or args.force:
        check_args=SimpleNamespace(**{**vars(args),'smoke':True,'verification':True})
        test_folder=prepare(check_args,nodes,saved)
        settings=read_json(test_folder/'fleet.json')
        deploy(test_folder,settings)
        started=parallel(nodes,lambda name,node:node_call(node,dict(action='start',job=settings['job'])))
        write_json(test_folder/'start-result.json',started)
        if failed_results(started):
            parallel(nodes,lambda name,node:node_call(node,dict(action='stop',job=settings['job'])))
            raise RuntimeError('Not all test workers started: '+json.dumps(started))
        deadline=time.monotonic()+3600
        previous=None
        while True:
            states=parallel(nodes,lambda name,node:node_call(node,dict(action='status',job=settings['job'])))
            summary={name:{key:state.get(key) for key in ('state','completed','total','running','error')}
                     for name,state in states.items()}
            if summary!=previous: print(json.dumps({'test_progress':summary}),flush=True); previous=summary
            if failed_results(states) or any(s.get('state') in ('paused','interrupted') for s in states.values()):
                parallel(nodes,lambda name,node:node_call(node,dict(action='stop',job=settings['job'])))
                raise RuntimeError('Readiness test failed; production was not started. '+json.dumps(summary))
            if all(s.get('state')=='complete' and s.get('validated') and not s.get('running') for s in states.values()): break
            if time.monotonic()>deadline:
                parallel(nodes,lambda name,node:node_call(node,dict(action='stop',job=settings['job'])))
                raise RuntimeError('Readiness test timed out; stop requested on all workers')
            time.sleep(5)
        dataset=fetch(test_folder,settings)
        if 'folder' not in dataset: raise RuntimeError('Test collection failed: '+json.dumps(dataset))
        certificates=parallel(nodes,lambda name,node:node_call(node,dict(action='mark_ready',job=settings['job'],
            release=release,runtime_signature=digest_json(runtime_config(node)),quality=args.quality,defects_only=args.defects_only)))
        if failed_results(certificates): raise RuntimeError('Readiness certification failed: '+json.dumps(certificates))
    if snapshot()[0]!=release:
        raise RuntimeError('The environment changed during verification. Run Ready again to test the new version')
    production_args=SimpleNamespace(**{**vars(args),'smoke':False})
    production=prepare(production_args,nodes,saved)
    deployment=deploy(production,read_json(production/'fleet.json'))
    result=dict(ready=True,release=release,production_run=str(production),
                images=args.count*len(nodes) if args.per_node else args.count,
                images_per_node=args.count if args.per_node else None,
                nodes=list(nodes),test_reused=checked and not args.force,test_dataset=dataset,
                updates=updates,deployment=deployment,checked_at=datetime.now().isoformat())
    write_json(ROOT/'.cache/fleet-ready.json',result)
    print(json.dumps(result,indent=2),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','start','status','stop','resume','fetch','doctor','sync','ready','launch','defects-only'))
    parser.add_argument('--config',type=Path,default=ROOT/'fleet_nodes.local.json')
    parser.add_argument('--nodes',default='desktop,spark,agx')
    parser.add_argument('--run',type=Path)
    parser.add_argument('--count',type=int,default=3200)
    parser.add_argument('--per-node',action='store_true',help='Generate Count images on EACH selected device with separate seed ranges')
    parser.add_argument('--defects-only',action=argparse.BooleanOptionalAction,default=None,help='Exclude good specimens from future production plans')
    parser.add_argument('--seed',type=int,default=None)
    parser.add_argument('--quality',choices=('quick','full'),default='full')
    parser.add_argument('--profile',choices=('reference','yolox'),default='yolox')
    parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--force',action='store_true',help='Repeat readiness renders even when this version was tested')
    args=parser.parse_args()
    if args.seed is None: args.seed=secrets.randbelow(1_900_000_000)
    configured=read_json(args.config)
    if not configured: raise RuntimeError('Configure fleet_nodes.local.json first; see remote/FLEET.md')
    if args.defects_only is None: args.defects_only=configured.get('defaults',{}).get('defects_only',False)
    nodes={safe_name(name):configured['nodes'][name] for name in args.nodes.split(',')}
    if args.action=='defects-only':
        from fleet_node import lock
        with lock(ROOT/'.cache/fleet-controller.lock'):
            folder=args.run or Path(read_json(ROOT/'.cache/fleet-active.json')['folder'])
            result=continue_defects(folder,read_json(folder/'fleet.json'))
            configured.setdefault('defaults',{})['defects_only']=True
            write_json(args.config,configured)
            print(json.dumps(result,indent=2))
        return
    if args.action=='sync':
        saved=snapshot()
        result=parallel(nodes,lambda name,node:sync_one(node,saved))
        write_json(ROOT/'.cache/fleet-sync.json',dict(release=saved[0],nodes=result))
        print(json.dumps(result,indent=2))
        if failed_results(result): sys.exit(1)
        return
    if args.action in ('ready','launch'):
        from fleet_node import lock
        with lock(ROOT/'.cache/fleet-controller.lock'):
            result=ready(args,nodes)
        if args.action=='ready': return
        # Launch is an explicit production request. Ready alone never starts it.
        args.action='start'; args.run=Path(result['production_run'])
    if args.action=='doctor':
        def probe(name,node):
            bootstrap(node)
            return dict(ready=node.get('ready',False),**node_call(node,dict(action='status')))
        print(json.dumps(parallel(nodes,probe),indent=2)); return
    if args.action in ('prepare','start') and not args.run:
        if args.action=='start' and any(not n.get('ready') for n in nodes.values()):
            raise RuntimeError('All selected nodes must pass GPU preflight before Start')
        folder=prepare(args,nodes)
        if args.action=='prepare': print(folder); return
    else:
        folder=args.run or Path(read_json(ROOT/'.cache/fleet-active.json')['folder'])
    settings=read_json(folder/'fleet.json')
    nodes={name:node for name,node in settings['nodes'].items() if name in args.nodes.split(',')}
    if not nodes: raise ValueError('None of the selected devices belongs to this saved run')
    settings={**settings,'nodes':nodes}
    if args.action=='start':
        if any(not n.get('ready') for n in nodes.values()): raise RuntimeError('A selected node is not ready')
        deploy(folder,settings)
        result=parallel(nodes,lambda name,node:node_call(node,dict(action='start',job=settings['job'])))
    elif args.action=='fetch': result=fetch(folder,settings)
    else: result=parallel(nodes,lambda name,node:node_call(node,dict(action=args.action,job=settings['job'])))
    write_json(folder/(args.action+'-result.json'),result)
    print(json.dumps(dict(run=str(folder),result=result),indent=2))
    if isinstance(result,dict) and any(isinstance(v,dict) and 'error' in v for v in result.values()): sys.exit(1)


if __name__=='__main__': main()
