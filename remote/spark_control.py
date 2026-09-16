"""Desktop-facing commands for this user's dedicated Spark render checkout."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rolling_supervisor import is_active, read


def current():
    pointer = read(ROOT/'exports/spark_captures/active_job.json')
    if not pointer:
        return None, dict(state='idle', saved=0, running=False)
    folder = Path(pointer['folder']).resolve()
    if folder.parent != (ROOT/'exports/spark_captures').resolve():
        raise RuntimeError('Active job is outside the Spark capture directory')
    status = read(folder/'status.json')
    return folder, dict(**status, running=is_active(folder), folder=str(folder),
                        supervisor=read(folder/'supervisor.json'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('status', 'start', 'stop', 'pack', 'require-idle'))
    parser.add_argument('--count', type=int, default=3000)
    parser.add_argument('--seed', type=int, default=910000)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    folder, status = current()
    if args.action == 'status':
        print(json.dumps(status, indent=2)); return
    if args.action == 'stop':
        if folder and status['running']:
            (folder/'cancel.flag').touch()
        print(json.dumps(dict(stop_requested=bool(folder and status['running'])))); return
    if status['running']:
        raise RuntimeError('A capture is running. Stop it and wait for the current image to finish first.')
    if args.action == 'require-idle':
        return
    if args.action == 'pack':
        if not folder:
            raise RuntimeError('There is no Spark capture to retrieve')
        archive = ROOT/'.cache/spark-transfers'/(folder.name+'.tar.gz')
        archive.parent.mkdir(parents=True, exist_ok=True)
        temporary = archive.with_suffix('.tmp')
        subprocess.run(['tar', '-I', 'gzip -1', '-cf', str(temporary), '-C', str(folder.parent), folder.name], check=True)
        temporary.replace(archive)
        print(json.dumps(dict(archive=str(archive), job=folder.name, bytes=archive.stat().st_size))); return
    # The lock prevents two desktop starts racing before active_job.json exists.
    import fcntl
    lock_path = ROOT/'.cache/spark-start.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if current()[1]['running']:
            raise RuntimeError('A capture was started by another request')
        log_path = ROOT/'.cache'/f'spark-start-{time.time_ns()}.log'
        command = ['bash', str(ROOT/'remote/blender_spark.sh'), '--background',
                   str(ROOT/'examples/rolling-shells/Rolling shell capture.blend'),
                   '--python-exit-code', '1', '--python', str(ROOT/'remote/spark_job.py'),
                   '--', '--count', str(args.count), '--seed', str(args.seed)]
        if args.smoke: command.append('--smoke')
        with log_path.open('w') as log:
            result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            print(log_path.read_text()[-12000:], file=sys.stderr)
            raise RuntimeError(f'Capture setup failed; see {log_path}')
        print(json.dumps(current()[1], indent=2))


if __name__ == '__main__':
    main()
