"""Restrict future classes in an immutable continuation; preserve outputs and device activity."""
import argparse
from datetime import datetime
from pathlib import Path
import time

from fleet import ROOT,bootstrap,failed_results,node_call,parallel,runtime_config
from fleet_common import digest_json,read_json,split_plan,write_json
from fleet_node import lock
from domain_plan import defects_only_plan,restrict_defect_kinds,validate_domain_plan
from roll_fleet_update import recount


def restrict(request_path, allowed):
    request=read_json(request_path)
    parent=Path(request['parent']); settings=read_json(parent/'fleet.json'); nodes=settings['nodes']
    if Path(read_json(ROOT/'.cache/fleet-active.json')['folder']).resolve()!=parent.resolve():
        raise RuntimeError('Active fleet changed; refusing to replace another run')
    states=parallel(nodes,lambda name,node:node_call(node,dict(action='status')))
    if any(s.get('job')!=settings['job'] for s in states.values()): raise RuntimeError('Active node job changed')
    for name,node in nodes.items():
        if states[name]['running']: node_call(node,dict(action='stop',job=settings['job']))
    deadline=time.monotonic()+900
    while any(s['running'] for s in states.values()):
        if time.monotonic()>deadline: raise TimeoutError('Waiting for image boundary')
        time.sleep(2)
        states=parallel(nodes,lambda name,node:node_call(node,dict(action='status')))
        if any(s.get('job')!=settings['job'] for s in states.values()): raise RuntimeError('Active node job changed')
    plan=read_json(parent/'render_plan.json')
    if digest_json(plan)!=settings['source_plan_sha256']: raise ValueError('Parent plan hash changed')
    preserved=[]
    for name in nodes:
        shard=defects_only_plan(read_json(parent/(name+'.plan.json')),states[name]['completed'])
        shard=restrict_defect_kinds(shard,allowed,states[name]['completed'])
        preserved.extend(shard['generation_policy']['preserved_sample_ids'])
        for index,row in zip(settings['assignments'][name],shard['samples']): plan['samples'][index]=row
    plan['generation_policy']=dict(defects_only=True,allowed_defects=allowed,preserved_sample_ids=preserved)
    recount(plan);validate_domain_plan(plan)
    shards=split_plan(plan,settings['assignments'])
    job=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_shapes'
    target=ROOT/'exports/fleet_runs'/job;target.mkdir(parents=True)
    inactive=[n for n,s in request['initial_states'].items() if not s['running']]
    write_json(target/'render_plan.json',plan)
    write_json(target/'fleet.json',{**settings,'job':job,'source_plan_sha256':digest_json(plan),
        'continued_from':str(parent),'paused_nodes':inactive,'allowed_defects':allowed})
    for name,shard in shards.items(): write_json(target/(name+'.plan.json'),shard)
    write_json(request_path,{**request,'continuation':str(target),'paused_states':states})
    def carry(name,node):
        bootstrap(node)
        return node_call(node,dict(action='continue_defects',job=job,parent_job=settings['job'],
            plan=shards[name],completed=states[name]['completed'],paused=True,
            config={**runtime_config(node),'release':settings['release']}))
    deployed=parallel(nodes,carry);write_json(target/'deployment.json',deployed)
    if failed_results(deployed): raise RuntimeError('Continuation needs attention: '+str(deployed))
    write_json(ROOT/'.cache/fleet-active.json',dict(folder=str(target)))
    write_json(parent/'continued_to.json',dict(folder=str(target),reason='Soap and oil stains disabled for future images'))
    configured=read_json(ROOT/'fleet_nodes.local.json')
    configured.setdefault('defaults',{}).update(defects_only=True,allowed_defects=allowed)
    write_json(ROOT/'fleet_nodes.local.json',configured)
    started=parallel({n:node for n,node in nodes.items() if n not in inactive},
                     lambda name,node:node_call(node,dict(action='start',job=job)))
    write_json(target/'start-result.json',started)
    if failed_results(started): raise RuntimeError('Launch needs attention: '+str(started))
    result=dict(run=str(target),allowed_defects=allowed,preserved=len(preserved),paused=inactive,started=started)
    print(result,flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,required=True)
    parser.add_argument('--allowed',nargs='+',required=True,choices=('FOLD','DENT','SOAP_STAIN','OIL_STAIN'))
    args=parser.parse_args()
    with lock(ROOT/'.cache/fleet-controller.lock'): restrict(args.request,args.allowed)
