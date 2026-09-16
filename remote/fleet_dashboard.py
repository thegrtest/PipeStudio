"""Read-only fleet progress and cached image previews over local files and SSH."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import hashlib
import os
from pathlib import Path
import threading
import time
import shlex
from urllib.parse import urlsplit

from fleet import ROOT, node_call, run
from fleet_common import read_json, write_json
from fleet_node import status as local_status
from fleet_preview import create_preview


def load_preview(node, state):
    arguments = [node['root'], state['job'], state['last_image']]
    if node['transport'] == 'local':
        return create_preview(*arguments)
    # No installation or worker restart: run the read-only thumbnail helper
    # through the existing SSH connection and transfer only its JPEG output.
    script = (Path(__file__).parent/'fleet_preview.py').read_text(encoding='utf-8')
    command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', node['alias'],
               shlex.join([node['python'], '-c', script, *arguments])]
    data = run(command, timeout=12)
    if not data.startswith(b'\xff\xd8') or len(data) > 1024*1024:
        raise ValueError('Invalid preview response')
    return data


class Monitor:
    def __init__(self, config, interval=15):
        self.config = config
        self.interval = interval
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.previews = {}
        self.cached = dict(application='PipeStudioFleet', interval=interval, updated=None, nodes=[])

    def update_preview(self, name, node, state):
        job, image = state.get('job'), state.get('last_image')
        with self.lock:
            entries = self.previews.get(name, {})
            if entries and next(reversed(entries.values()))['job'] != job:
                self.previews.pop(name, None)
                entries = {}
            previous = next(reversed(entries.values()), None)
        if not image or not job:
            return dict(preview=None)
        token = hashlib.sha256((job+'\0'+image).encode()).hexdigest()[:24]
        if previous and previous['token'] == token:
            return dict(preview=previous['info'], preview_stale=False)
        try:
            data = load_preview(node, state)
            info = dict(url=f'/api/preview/{name}/{token}.jpg',
                        sample_id=Path(image).stem, checked=datetime.now(timezone.utc).isoformat())
            entry = dict(job=job, token=token, data=data, info=info)
            with self.lock:
                entries = self.previews.setdefault(name, {})
                entries[token] = entry
                # Keep the previous version briefly for browser requests racing
                # the next poll; memory and transfer cost stay bounded.
                while len(entries) > 2:
                    del entries[next(iter(entries))]
            return dict(preview=info, preview_stale=False)
        except Exception:
            # Preview failures must not turn a healthy renderer into an error.
            return dict(preview=previous['info'] if previous else None, preview_stale=True)

    def preview(self, name, token):
        with self.lock:
            entry = self.previews.get(name, {}).get(token)
            return entry['data'] if entry else None

    def probe(self, name, node):
        labels = {'desktop': 'Desktop', 'spark': 'DGX Spark', 'agx': 'AGX Orin'}
        result = dict(id=name, name=labels.get(name, name), ready=bool(node.get('ready')))
        if not node.get('ready') and not node.get('access_ready'):
            return {**result, 'state': 'setup_pending', 'running': False, 'completed': None,
                    'detail': 'GPU setup or unattended SSH access is not yet ready.'}
        try:
            state = local_status(Path(node['root'])) if node['transport'] == 'local' else node_call(node, {'action': 'status'})
            if not node.get('ready') and not state.get('running'):
                state.update(state='setup_pending', detail='Connected. GPU generation validation is still pending.')
            preview = self.update_preview(name, node, state)
            return {**result, **state, **preview, 'reachable': True, 'checked': datetime.now(timezone.utc).isoformat()}
        except Exception as error:
            with self.lock:
                previous = next((n for n in self.cached['nodes'] if n['id'] == name), {})
            return {**previous, **result, 'state': 'unreachable', 'running': False, 'reachable': False,
                    'detail': str(error)[-500:], 'preview_stale': True}

    def poll(self):
        config = read_json(self.config, {})
        nodes = config.get('nodes', {})
        with ThreadPoolExecutor(max_workers=max(1, len(nodes))) as workers:
            futures = [workers.submit(self.probe, name, node) for name, node in nodes.items()]
            results = [future.result() for future in futures]
        with self.lock:
            self.cached = dict(application='PipeStudioFleet', interval=self.interval,
                updated=datetime.now(timezone.utc).isoformat(), nodes=results)

    def loop(self):
        while not self.stop.is_set():
            try: self.poll()
            except Exception as error:
                with self.lock: self.cached['error'] = str(error)
            self.stop.wait(self.interval)

    def snapshot(self):
        with self.lock: return json.loads(json.dumps(self.cached))


def handler_for(monitor):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass

        def do_GET(self):
            route = urlsplit(self.path).path
            cache_control = 'no-store'
            if route in ('/api/status', '/health'):
                content = json.dumps(monitor.snapshot()).encode()
                mime = 'application/json; charset=utf-8'
            elif route in ('/', '/index.html'):
                content = (Path(__file__).parent/'fleet_dashboard.html').read_bytes()
                mime = 'text/html; charset=utf-8'
            elif route.startswith('/api/preview/'):
                parts = route.split('/')
                if len(parts) != 5 or not parts[4].endswith('.jpg'):
                    self.send_error(404); return
                content = monitor.preview(parts[3], parts[4][:-4])
                if content is None:
                    self.send_error(404); return
                mime = 'image/jpeg'
                cache_control = 'private, max-age=86400, immutable'
            else:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', cache_control)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers(); self.wfile.write(content)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, default=ROOT/'fleet_nodes.local.json')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--interval', type=int, default=15)
    args = parser.parse_args()
    monitor = Monitor(args.config, max(10, args.interval))
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(monitor))
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_port}'
    receipt = ROOT/'.cache/fleet-dashboard/server.json'
    write_json(receipt, dict(url=url, pid=os.getpid(), started=datetime.now(timezone.utc).isoformat()))
    thread = threading.Thread(target=monitor.loop, daemon=True); thread.start()
    print(url, flush=True)
    try: server.serve_forever(poll_interval=.5)
    finally:
        monitor.stop.set(); server.server_close()


if __name__ == '__main__': main()
