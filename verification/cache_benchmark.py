"""Matched full-quality Cycles cache trial, isolated from fleet production jobs."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

CACHE_MODES = {0: 'off', 1: 'on', 2: 'beauty_only', 3: 'off_repeat', 4: 'production'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def render(root, group, cache):
    request = read(root/'request.json')
    release = Path(request['release_path'])
    sys.path.insert(0, str(release))
    import bpy
    import pipe_studio as studio
    import domain_render
    from fast_pipeline import install
    from generate_domain_dataset import source_signature
    assert source_signature() == request['renderer_sources']
    install(studio)
    configure = studio.configure_renderer

    enabled = cache in (1, 2, 4)

    def configured(scene):
        configure(scene)
        scene.render.use_persistent_data = enabled

    if cache != 4: studio.configure_renderer = configured
    if cache == 2:
        set_mask = studio.set_mask_mode

        def uncached_masks(scene, active):
            scene.render.use_persistent_data = not active
            return set_mask(scene, active)

        studio.set_mask_mode = uncached_masks
    studio.register()
    scene = studio.fresh_scene()
    studio.setup_scene(scene)
    assert scene.render.use_persistent_data == enabled
    output = root/CACHE_MODES[cache]
    records = []
    for row in request['groups'][group]:
        started = time.perf_counter()
        info = domain_render.render_sample(studio, scene, row, output)
        elapsed = time.perf_counter() - started
        assert scene.render.use_persistent_data == enabled
        assert scene.cycles.samples == row['settings']['samples'] == 128
        records.append(dict(sample_id=row['sample_id'], seconds=elapsed,
                            cache=CACHE_MODES[cache], setup=row['setup'],
                            glare_retries=info['glare_guard']['retries'],
                            instances=len(info['instances']),
                            width=info['width'], height=info['height']))
        write(output/f'timings_{group}.json', records)
        print('CACHE_BENCH_SAMPLE '+json.dumps(records[-1]), flush=True)


def compare(root, candidate='on', groups=None):
    import numpy as np
    from PIL import Image
    request = read(root/'request.json')
    groups = list(range(len(request['groups']))) if groups is None else groups
    timings = {mode: {r['sample_id']: r for g in groups
                     for r in read(root/mode/f'timings_{g}.json')}
               for mode in ('off', candidate)}
    rows = []
    for recipe in sum([request['groups'][g] for g in groups], []):
        sid = recipe['sample_id']
        a, b = (read(root/m/'metadata'/f'{sid}.json') for m in ('off', candidate))
        image_a, image_b = (np.asarray(Image.open(root/m/'images'/f'{sid}.png').convert('RGB'))
                            for m in ('off', candidate))
        diff = np.abs(image_a.astype(np.int16)-image_b.astype(np.int16))
        mask_checks = []
        for rel in [a['pipe_mask']] + [i['mask'] for i in a['instances']]:
            x, y = (np.asarray(Image.open(root/m/rel).convert('L')) > 127 for m in ('off', candidate))
            union = int(np.count_nonzero(x | y))
            mask_checks.append(dict(mask=rel, exact=bool(np.array_equal(x, y)),
                                    different_pixels=int(np.count_nonzero(x != y)),
                                    iou=float(np.count_nonzero(x & y)/union) if union else 1.0))
        row = dict(sample_id=sid, setup=recipe['setup'],
                   off_seconds=timings['off'][sid]['seconds'], on_seconds=timings[candidate][sid]['seconds'],
                   pixels_exact=bool(np.array_equal(image_a, image_b)),
                   mean_abs_rgb_difference=float(diff.mean()), max_rgb_difference=int(diff.max()),
                   changed_pixel_fraction=float(np.any(diff != 0, axis=2).mean()),
                   labels_exact=(root/'off/labels'/f'{sid}.txt').read_bytes() == (root/candidate/'labels'/f'{sid}.txt').read_bytes(),
                   metadata_exact=a == b, masks=mask_checks,
                   glare_retries_off=a['glare_guard']['retries'], glare_retries_on=b['glare_guard']['retries'])
        rows.append(row)
    off = sum(r['off_seconds'] for r in rows)
    on = sum(r['on_seconds'] for r in rows)
    report = dict(release=request['release'], candidate=candidate, samples=len(rows), off_seconds=off, on_seconds=on,
                  throughput_gain_percent=(off/on-1)*100, time_saved_percent=(1-on/off)*100,
                  all_images_exact=all(r['pixels_exact'] for r in rows),
                  all_labels_exact=all(r['labels_exact'] for r in rows),
                  all_masks_exact=all(m['exact'] for r in rows for m in r['masks']),
                  all_metadata_exact=all(r['metadata_exact'] for r in rows), samples_detail=rows)
    write(root/f'comparison_{candidate}.json', report)
    if candidate == 'on': write(root/'comparison.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'samples_detail'}), flush=True)
    return report


def run(root):
    request = read(root/'request.json')
    config = request['config']
    env = os.environ.copy()
    env.update(config.get('env', {}))
    runs = []
    write(root/'status.json', dict(state='running', pid=os.getpid(), runs=runs))
    try:
        protocol = request.get('protocol', [dict(group=g, cache=c)
                   for g in range(len(request['groups'])) for c in ((0, 1) if g % 2 == 0 else (1, 0))])
        for step in protocol:
            group, cache = step['group'], step['cache']
            mode = CACHE_MODES[cache]
            command = [p.replace('{release}', request['release_path']) for p in config['blender']]
            command += ['-b', '--factory-startup', '-t', str(config['threads']),
                        '--python-exit-code', '1', '--python', str(Path(__file__).resolve()),
                        '--', 'render', '--root', str(root), '--group', str(group), '--cache', str(cache)]
            started = time.perf_counter()
            with (root/f'{mode}_{group}.log').open('w') as log:
                result = subprocess.run(command, cwd=request['release_path'], env=env,
                                        stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                        timeout=1800)
            run_info = dict(group=group, cache=mode, returncode=result.returncode,
                            wall_seconds=time.perf_counter()-started)
            runs.append(run_info)
            write(root/'status.json', dict(state='running', pid=os.getpid(), runs=runs))
            print(json.dumps(run_info), flush=True)
            if result.returncode:
                raise RuntimeError(f'Benchmark failed: {mode}_{group}.log')
        report = compare(root, request.get('candidate', 'on'))
        if (root/'off_repeat/timings_0.json').exists(): compare(root, 'off_repeat', [0])
        write(root/'status.json', dict(state='complete', runs=runs,
                                       images_exact=report['all_images_exact'], labels_exact=report['all_labels_exact']))
    except Exception as error:
        write(root/'status.json', dict(state='failed', runs=runs, error=str(error)))
        raise


def guarded_run(root):
    request = read(root/'request.json')
    production = request.get('pause_production')
    if not production:
        return run(root)
    node_root = Path(production['root'])
    sys.path.insert(0, str(node_root/'bin'))
    from fleet_node import action, busy, lock, status
    state = status(node_root)
    job = production['job']
    assert state['job'] == job and state['running'], state
    flag = node_root/'jobs'/job/'cancel.flag'
    assert not flag.exists(), 'Production already has a stop request'
    stopped = False
    try:
        action(node_root, dict(action='stop', job=job))
        stopped = True
        write(root/'status.json', dict(state='waiting_for_image_boundary', production_job=job))
        deadline = time.monotonic() + 900
        while busy(node_root):
            if time.monotonic() > deadline:
                raise TimeoutError('Production did not reach an image boundary')
            time.sleep(1)
        with lock(node_root/'worker.lock'):
            run(root)
    finally:
        if stopped:
            current = status(node_root)
            if current['job'] == job and not current['running'] and current['state'] == 'paused':
                resumed = action(node_root, dict(action='resume', job=job))
                write(root/'production_resumed.json', resumed)
            elif current['job'] == job and current['running']:
                flag.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'render', 'compare'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--group', type=int, default=0)
    parser.add_argument('--cache', type=int, choices=tuple(CACHE_MODES), default=0)
    parser.add_argument('--candidate', choices=tuple(CACHE_MODES.values()), default='on')
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else sys.argv[1:]
    args = parser.parse_args(argv)
    if args.action == 'render': render(args.root.resolve(), args.group, args.cache)
    elif args.action == 'compare': compare(args.root.resolve(), args.candidate)
    else: guarded_run(args.root.resolve())
