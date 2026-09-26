"""Bounded, resumable assembly rendering through the existing fleet node lock."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from assembly_generate import complete, finished, finalize


def supervise(root, job, lock):
    from fleet_common import read_json, write_json, digest_file, digest_json, inside
    folder = root / 'jobs' / job
    request = read_json(folder / 'fleet_job.json')
    release = root / 'releases' / request['release']
    plan = read_json(folder / 'render_plan.json')
    rows = plan['rows']; settings = plan['settings']
    verified = failures = 0
    started = time.monotonic()
    with lock(root / 'worker.lock'):
        try:
            if digest_json(plan) != request['plan_sha256']:
                raise ValueError('Saved assembly plan changed')
            for name, expected in read_json(release / 'release.json')['files'].items():
                if digest_file(inside(release, name)) != expected:
                    raise ValueError('Render snapshot changed: ' + name)
            ids = [row['sample_id'] for row in rows]
            if len(set(ids)) != len(ids) or len(rows) != settings['count']:
                raise ValueError('Assembly plan has duplicate IDs or incorrect count')
            env = {**os.environ, **request.get('env', {})}
            while True:
                # Verify only newly committed rows; a new supervisor verifies
                # the entire existing prefix before allowing it to be skipped.
                while verified < len(rows) and finished(folder, rows[verified]):
                    verified += 1
                state = 'complete' if verified == len(rows) else 'running'
                if state != 'complete' and ((folder / 'cancel.flag').exists() or (folder / 'STOP').exists()):
                    state = 'paused'
                result = dict(state=state, completed=verified, total=len(rows), pipeline='assembly',
                              accepted=len(list((folder/'metadata').glob('*.json'))),
                              rejected=len(list((folder/'rejections').glob('*.json'))),
                              pid=os.getpid(), failures=failures,
                              elapsed_seconds=round(time.monotonic() - started, 1))
                write_json(folder / 'fleet_status.json', result)
                if state != 'running':
                    break
                if shutil.disk_usage(folder).free < request.get('minimum_free_gb', 3) * 1024**3:
                    raise RuntimeError('Insufficient free disk space; free space and resume the saved assembly job')
                chunk = max(1, request.get('chunk', 3))
                command = [part.replace('{release}', str(release)) for part in request['blender']]
                command += ['-b', '--factory-startup', '-t', str(request.get('threads', 8)),
                            '--python-exit-code', '1', '--python', str(release / 'assembly_generate.py'), '--',
                            '--output', str(folder), '--fleet-plan', str(folder / 'render_plan.json'),
                            '--chunk', str(chunk), '--verified-prefix', str(verified), '--resume']
                for name in ('count', 'seed', 'samples', 'scale', 'look', 'lighting', 'defect_set'):
                    command += ['--' + name.replace('_', '-'), str(settings[name])]
                if not settings.get('strict_visibility',True):command.append('--no-strict-visibility')
                with (folder / 'render.log').open('a') as log:
                    try:
                        child = subprocess.run(command, cwd=release, env=env, stdin=subprocess.DEVNULL,
                                               stdout=log, stderr=subprocess.STDOUT,
                                               timeout=max(900, chunk * request.get('seconds_per_image', 300)),
                                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                        code = child.returncode
                    except subprocess.TimeoutExpired:
                        code = -999
                progressed = finished(folder, rows[verified])
                failures = 0 if progressed else failures + 1
                if failures >= 3:
                    raise RuntimeError(f'Three attempts made no progress (exit {code}); see render.log')
            if state == 'complete':
                finalize(folder, plan)
                with (folder / 'validation.log').open('w') as log:
                    checked = subprocess.run([sys.executable, str(release / 'verification/verify_assembly_track.py'), str(folder)],
                                             cwd=release, stdout=log, stderr=subprocess.STDOUT)
                if checked.returncode:
                    raise RuntimeError('Assembly label/mask validation failed; see validation.log')
                write_json(folder / 'status.json', dict(state='complete', completed=verified, total=len(rows)))
                write_json(folder / 'fleet_status.json', {**result, 'validated': True})
        except Exception as error:
            write_json(folder / 'fleet_status.json', dict(state='failed', completed=verified, total=len(rows),
                                                        pipeline='assembly', error=str(error), pid=os.getpid()))
            raise
