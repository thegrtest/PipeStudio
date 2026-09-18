"""Launch the refined assembly renderer on explicitly selected fleet devices."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import secrets
import sys
from types import SimpleNamespace

from fleet import ROOT, snapshot, deploy, parallel, node_call, failed_results
from fleet_common import read_json, write_json, digest_json, safe_name

sys.path.insert(0, str(ROOT))
from assembly_plan import make_plan
from assembly_generate import render_settings


def make_node_plan(count, seed, samples=96):
    if not 1 <= count <= 100000:
        raise ValueError('Count per device must be between 1 and 100000')
    args = SimpleNamespace(count=count, seed=seed, samples=samples, scale=1,
                           look='CAMERA_MATCHED', lighting='BALANCED', defect_set='DENTS_FOLDS')
    rows = make_plan(count, seed, args.look, args.lighting, args.defect_set)
    for row in rows:
        # Stable across a specimen's three views, independent of its class.
        value = int(hashlib.sha256((row['split_group'] + ':lighting').encode()).hexdigest()[:8], 16) / 2**32
        lighting = 'BALANCED' if value < .70 else 'CURRENT' if value < .85 else 'FOUR_LINES'
        for recipe in [row['recipe']] + row['companions']:
            recipe['lighting'] = lighting
    return dict(pipeline='assembly', settings=render_settings(args), rows=rows,
                policy=dict(lighting_weights=dict(BALANCED=.70, CURRENT=.15, FOUR_LINES=.15),
                            primary_conditions=dict(Counter(r['recipe']['condition'] for r in rows)),
                            lighting_counts=dict(Counter(r['recipe']['lighting'] for r in rows)),
                            nominal_class_ratios=dict(dent=.45, deformity=.45, good=.10)))


def prepare(nodes, count, seed, samples=96):
    # Separate ranges cover both primary and +100000 companion seeds.
    plans = {name: make_node_plan(count, seed + index * 1000000, samples)
             for index, name in enumerate(nodes)}
    groups = [{recipe['specimen_id'] for row in plan['rows'] for recipe in [row['recipe']] + row['companions']}
              for plan in plans.values()]
    if sum(map(len, groups)) != len(set().union(*groups)):
        raise ValueError('Device specimen ranges overlap')
    release, archive, archive_hash = snapshot()
    job = datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_assembly'
    folder = ROOT / 'exports/fleet_runs' / job
    folder.mkdir(parents=True, exist_ok=False)
    settings = dict(job=job, pipeline='assembly', release=release, archive=str(archive), archive_sha256=archive_hash,
                    nodes=nodes, count_per_node=count, samples=samples,
                    node_plan_sha256={name: digest_json(plan) for name, plan in plans.items()})
    write_json(folder / 'fleet.json', settings)
    for name, plan in plans.items():
        write_json(folder / (name + '.plan.json'), plan)
    # Standard status/stop/resume tools and dashboard use the same node jobs.
    write_json(ROOT / '.cache/fleet-active.json', dict(folder=str(folder)))
    write_json(ROOT / '.cache/assembly-fleet-active.json', dict(folder=str(folder)))
    return folder, settings


def fetch(folder, settings):
    """Retrieve full, separate per-node assembly datasets without mixing schemas."""
    import shutil
    import tarfile
    from fleet import run
    from fleet_common import digest_file, inside
    def one(name, node):
        package = node_call(node, dict(action='pack', job=settings['job']))
        destination = folder / 'nodes' / name
        destination.mkdir(parents=True, exist_ok=True)
        archive = destination / (settings['job'] + '.tgz')
        if node['transport'] == 'local':
            shutil.copyfile(package['archive'], archive)
        else:
            run(['scp', '-q', '-o', 'BatchMode=yes', node['alias'] + ':' + package['archive'], str(archive)])
        if digest_file(archive) != package['sha256']:
            raise ValueError('Assembly transfer checksum mismatch')
        with tarfile.open(archive) as data:
            for member in data:
                if member.issym() or member.islnk():
                    # Tracking RGB uses hard links to the defect RGB. The tar
                    # extractor validates their targets against the dataset root.
                    inside(destination, member.linkname)
                elif not (member.isfile() or member.isdir()):
                    raise ValueError('Unexpected assembly archive entry')
                inside(destination, member.name)
                data.extract(member, destination, filter='data')
        return dict(folder=str(destination / settings['job']))
    result = parallel(settings['nodes'], one)
    write_json(folder / 'retrieval.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'launch', 'start', 'status', 'stop', 'resume', 'fetch'))
    parser.add_argument('--nodes', default='spark,agx')
    parser.add_argument('--count', type=int, default=5000, help='Images per selected device')
    parser.add_argument('--seed', type=int)
    parser.add_argument('--samples', type=int, default=96)
    parser.add_argument('--run', type=Path)
    args = parser.parse_args()
    config = read_json(ROOT / 'fleet_nodes.local.json')
    names = [safe_name(name) for name in args.nodes.split(',')]
    nodes = {name: config['nodes'][name] for name in names}
    if args.action in ('prepare', 'launch'):
        states = parallel(nodes, lambda name, node: node_call(node, dict(action='status')))
        if failed_results(states) or any(s.get('running') for s in states.values()):
            raise RuntimeError('Selected devices must be reachable and idle: ' + json.dumps(states))
        folder, settings = prepare(nodes, args.count, args.seed if args.seed is not None else secrets.randbelow(1_500_000_000), args.samples)
        if args.action == 'prepare':
            print(folder); return
    else:
        folder = args.run or Path(read_json(ROOT / '.cache/assembly-fleet-active.json')['folder'])
        settings = read_json(folder / 'fleet.json')
        if settings.get('pipeline') != 'assembly':
            raise ValueError('This is not an assembly fleet job')
        settings = {**settings, 'nodes': {name: node for name, node in settings['nodes'].items() if name in names}}
        if not settings['nodes']:
            raise ValueError('No selected nodes belong to this assembly job')
    if args.action in ('launch', 'start'):
        deploy(folder, settings)
        result = parallel(settings['nodes'], lambda name, node: node_call(node, dict(action='start', job=settings['job'])))
    elif args.action == 'fetch':
        result = fetch(folder, settings)
    else:
        result = parallel(settings['nodes'], lambda name, node: node_call(node, dict(action=args.action, job=settings['job'])))
    write_json(folder / (args.action + '-result.json'), result)
    print(json.dumps(dict(run=str(folder), result=result), indent=2))
    if failed_results(result):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
