from pathlib import Path
import io
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parent/'remote'))
from fleet_common import write_json
from fleet_dashboard import Monitor
from fleet_node import lock, status
from fleet_preview import create_preview
from PIL import Image
from test_domain_runtime import fixture


class DashboardTests(unittest.TestCase):
    def test_preview_is_small_preserves_aspect_and_cannot_read_outside_job(self):
        with fixture() as root:
            source=root/'jobs/test/all/images/pipe.png'
            source.parent.mkdir(parents=True)
            Image.new('RGB',(1600,2000),'#ad986e').save(source)
            original=source.read_bytes()
            data=create_preview(root,'test',str(source))
            with Image.open(io.BytesIO(data)) as result:
                self.assertEqual(result.format,'JPEG')
                self.assertEqual(result.size,(576,720))
            self.assertEqual(source.read_bytes(),original)
            for job,path in (('other',source),('../test',source),('test',root/'outside.png')):
                with self.assertRaises(ValueError): create_preview(root,job,str(path))

    def test_unchanged_image_is_not_downloaded_and_only_two_previews_are_kept(self):
        monitor=Monitor(Path('unused.json'))
        state=dict(job='test',last_image='images/one.png')
        with patch('fleet_dashboard.load_preview',return_value=b'jpeg') as fetch:
            first=monitor.update_preview('spark',{},state)
            self.assertEqual(first,monitor.update_preview('spark',{},state))
            fetch.assert_called_once()
            monitor.update_preview('spark',{},dict(state,last_image='images/two.png'))
            monitor.update_preview('spark',{},dict(state,last_image='images/three.png'))
        self.assertEqual(len(monitor.previews['spark']),2)
        self.assertIsNone(monitor.preview('spark',first['preview']['url'].split('/')[-1][:-4]))
        self.assertIsNone(monitor.preview('../secret','anything'))

    def test_failed_preview_keeps_counts_and_last_image_but_never_crosses_jobs(self):
        monitor=Monitor(Path('unused.json'))
        old=dict(job='test',last_image='images/one.png')
        with patch('fleet_dashboard.load_preview',return_value=b'jpeg'):
            first=monitor.update_preview('spark',{},old)
        state=dict(job='test',last_image='images/two.png',state='running',running=True,completed=9)
        with patch('fleet_dashboard.node_call',return_value=state), patch('fleet_dashboard.load_preview',side_effect=TimeoutError):
            result=monitor.probe('spark',dict(ready=True,transport='ssh'))
            self.assertTrue(result['running'])
            self.assertTrue(result['reachable'])
            self.assertEqual(result['completed'],9)
            self.assertEqual(result['preview'],first['preview'])
            self.assertTrue(result['preview_stale'])
            changed=monitor.update_preview('spark',{},dict(state,job='new'))
            self.assertIsNone(changed['preview'])
            self.assertNotIn('spark',monitor.previews)

    def test_pending_device_does_not_attempt_access_or_invent_count(self):
        monitor=Monitor(Path('unused.json'))
        with patch('fleet_dashboard.node_call') as call:
            result=monitor.probe('agx',{'ready':False})
        call.assert_not_called()
        self.assertIsNone(result['completed'])
        self.assertEqual(result['state'],'setup_pending')

    def test_disconnected_device_retains_last_known_count(self):
        monitor=Monitor(Path('unused.json'))
        monitor.cached['nodes']=[dict(id='spark',completed=82,total=100)]
        with patch('fleet_dashboard.node_call',side_effect=TimeoutError('SSH timed out')):
            result=monitor.probe('spark',dict(ready=True,transport='ssh'))
        self.assertEqual(result['completed'],82)
        self.assertFalse(result['running'])
        self.assertEqual(result['state'],'unreachable')

    def test_connected_device_can_report_counts_before_gpu_is_ready(self):
        monitor=Monitor(Path('unused.json'))
        with patch('fleet_dashboard.node_call',return_value=dict(state='idle',running=False,completed=0)):
            result=monitor.probe('agx',dict(ready=False,access_ready=True,transport='ssh'))
        self.assertEqual(result['completed'],0)
        self.assertTrue(result['reachable'])
        self.assertEqual(result['state'],'setup_pending')

    def test_running_worker_reports_committed_per_image_progress(self):
        with fixture() as root:
            write_json(root/'active.json',{'job':'test'})
            folder=root/'jobs/test'
            write_json(folder/'fleet_status.json',dict(state='running',completed=0,total=8))
            write_json(folder/'progress.json',dict(completed=5,total=8,last_image='image5.png'))
            with lock(root/'worker.lock'):
                result=status(root)
            self.assertEqual(result['completed'],5)
            self.assertEqual(result['last_image'],'image5.png')
            self.assertTrue(result['running'])


if __name__=='__main__': unittest.main()
