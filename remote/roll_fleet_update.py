"""Stage project updates live, then switch each device at an image boundary."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime
import json
from pathlib import Path
import shlex
import sys
import time

from fleet import ROOT,bootstrap,copy_to,failed_results,node_call,parallel,patch_archive,run,runtime_config,snapshot,source_manifest
from fleet_common import digest_file,digest_json,read_json,write_json
from fleet_node import lock


def staged_update(node,saved):
    release,archive,archive_hash=saved
    if digest_file(archive)!=archive_hash: raise ValueError('Source snapshot changed')
    relative='update_tools/'+release[:16]
    folder=str(Path(node['root'])/relative).replace('\\','/')
    arguments=[node['python'],'-c','from pathlib import Path; import sys; Path(sys.argv[1]).mkdir(parents=True,exist_ok=True)',folder]
    run(arguments if node['transport']=='local' else ['ssh','-o','BatchMode=yes',node['alias'],shlex.join(arguments)],timeout=30)
    for name in ('fleet_common.py','fleet_node.py','release_store.py','stage_fleet_update.py'):
        copy_to(node,ROOT/'remote'/name,relative+'/'+name)
    def call(request):
        args=[node['python'],folder+'/stage_fleet_update.py',node['root']]
        cmd=args if node['transport']=='local' else ['ssh','-o','BatchMode=yes',node['alias'],shlex.join(args)]
        return json.loads(run(cmd,input=json.dumps(request).encode(),timeout=180))
    files=source_manifest(archive); req=dict(release=release,files=files)
    offered=call(dict(action='offer',**req))
    if offered['installed']: return dict(release=release,changed=0,bytes_sent=0)
    patch=patch_archive(archive,release,offered['missing'])
    copy_to(node,patch,'incoming/'+patch.name)
    installed=call(dict(action='install',archive=patch.name,sha256=digest_file(patch),base_release=offered['base_release'],**req))
    return {**installed,'release':release,'bytes_sent':patch.stat().st_size}


def merged_plan(old,latest,completed):
    from domain_plan import validate_domain_plan
    if not 0<=completed<=len(old['samples']): raise ValueError('Invalid completion count')
    lookup={r['sample_id']:r for r in latest['samples']}
    if set(lookup)!={r['sample_id'] for r in old['samples']}: raise ValueError('New profile changed specimen identities')
    plan=deepcopy(latest)
    plan['samples']=deepcopy(old['samples'][:completed])+[deepcopy(lookup[r['sample_id']]) for r in old['samples'][completed:]]
    plan['generation_policy']={**latest.get('generation_policy',{}),'defects_only':True,
                               'preserved_sample_ids':[r['sample_id'] for r in old['samples'][:completed]]}
    recount(plan)
    return validate_domain_plan(plan)


def recount(plan):
    rows=plan['samples']
    plan['expected_primary_counts']=dict(Counter(r['primary_kind'] for r in rows))
    plan['expected_instance_counts']=dict(Counter(i['kind'] for r in rows for i in r['instances']))
    plan['expected_setup_counts']=dict(Counter(r['setup'] for r in rows))


def rollout(parent,paused):
    from domain_plan import make_plan,defects_only_plan,validate_domain_plan,restrict_defect_kinds
    settings=read_json(parent/'fleet.json'); nodes=settings['nodes']
    saved=snapshot(); release=saved[0]
    old_plans={n:read_json(parent/(n+'.plan.json')) for n in nodes}
    # Use the latest production profile, with the same independent seed ranges.
    latest={n:defects_only_plan(make_plan(len(p['samples']),min(r['settings']['seed'] for r in p['samples']),
                                      quality=p['quality'],profile='yolox')) for n,p in old_plans.items()}
    allowed=read_json(ROOT/'fleet_nodes.local.json',{}).get('defaults',{}).get('allowed_defects')
    if allowed: latest={n:restrict_defect_kinds(p,allowed) for n,p in latest.items()}
    if snapshot()[0]!=release: raise RuntimeError('Project changed while planning; retry the update')
    stages=parallel(nodes,lambda name,node:staged_update(node,saved))
    print(json.dumps(dict(staged=stages)),flush=True)
    if failed_results(stages): raise RuntimeError('Staging failed; active remote workers were not stopped')
    job=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_update'
    folder=ROOT/'exports/fleet_runs'/job; folder.mkdir(parents=True)
    shards={}; receipts={}; started={}
    write_json(folder/'update-request.json',dict(parent=str(parent),release=release,paused=list(paused)))
    for name,node in nodes.items():
        node_call(node,dict(action='stop',job=settings['job']))
        deadline=time.monotonic()+900
        while True:
            state=node_call(node,dict(action='status',job=settings['job']))
            if not state['running']: break
            if time.monotonic()>deadline: raise RuntimeError('Timed out waiting for '+name+' current image')
            time.sleep(2)
        try:
            bootstrap(node)
            shard=merged_plan(old_plans[name],latest[name],state['completed'])
            shard['fleet_node']=name
            write_json(folder/(name+'.plan.json'),shard); shards[name]=shard
            config={**runtime_config(node),'release':release}
            receipts[name]=node_call(node,dict(action='continue_release',job=job,parent_job=settings['job'],
                completed=state['completed'],plan=shard,config=config,paused=name in paused))
            node_call(node,dict(action='stage_release',release=release,files=source_manifest(saved[1])))
            if name not in paused:
                started[name]=node_call(node,dict(action='start',job=job))
            print(json.dumps(dict(device=name,paused=name in paused,**receipts[name])),flush=True)
            write_json(folder/'update-progress.json',dict(deployed=receipts,started=started))
        except Exception:
            if name not in paused:
                current=node_call(node,dict(action='status'))
                if not current['running']: node_call(node,dict(action='resume',job=settings['job']))
            raise
    plan=deepcopy(next(iter(latest.values())))
    original=read_json(parent/'render_plan.json')
    plan['samples']=deepcopy(original['samples']); preserved=[]
    for name,shard in shards.items():
        preserved.extend(shard['generation_policy']['preserved_sample_ids'])
        for index,row in zip(settings['assignments'][name],shard['samples']): plan['samples'][index]=row
    plan['generation_policy']={**plan.get('generation_policy',{}),'defects_only':True,'preserved_sample_ids':preserved}
    recount(plan); validate_domain_plan(plan)
    write_json(folder/'render_plan.json',plan)
    write_json(folder/'fleet.json',{**settings,'job':job,'release':release,'archive':str(saved[1]),'archive_sha256':saved[2],
        'source_plan_sha256':digest_json(plan),'continued_from':str(parent),'paused_nodes':list(paused)})
    write_json(folder/'deployment.json',receipts); write_json(folder/'start-result.json',started)
    write_json(ROOT/'.cache/fleet-active.json',dict(folder=str(folder)))
    write_json(parent/'continued_to.json',dict(folder=str(folder),reason='Latest project update at image boundaries'))
    print(json.dumps(dict(run=str(folder),release=release,paused=list(paused),started=started,preserved=len(preserved)),indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--pause',default='desktop')
    args=parser.parse_args()
    parent=args.run or Path(read_json(ROOT/'.cache/fleet-active.json')['folder'])
    with lock(ROOT/'.cache/fleet-controller.lock'):
        rollout(parent,set(filter(None,args.pause.split(','))))
