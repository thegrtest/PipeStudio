import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid
import shutil
from contextlib import contextmanager
from generate_domain_dataset import check_committed,exclusive
from domain_render import atomic_json


@contextmanager
def fixture():
    parent=(Path(__file__).parent/'verification'/'.domain-runtime-tests').resolve()
    path=parent/uuid.uuid4().hex
    path.mkdir(parents=True)
    try:yield path
    finally:
        if path.resolve().is_relative_to(parent) and path.resolve()!=parent:
            shutil.rmtree(path)


class RuntimeTests(unittest.TestCase):
    def test_local_eval_gap_cli_prepares_training_and_preview_plans(self):
        import json
        import subprocess
        import sys
        repo=Path(__file__).resolve().parent
        with fixture() as temp:
            for preview,count in ((False,60),(True,18)):
                output=temp/('preview' if preview else 'production')
                command=[sys.executable,str(repo/'generate_domain_dataset.py'),
                         '--output',str(output),'--profile','eval-gap','--count','60',
                         '--seed','925010000' if preview else '925000000','--prepare-only']
                if preview:command.append('--preview')
                result=subprocess.run(command,capture_output=True,text=True,cwd=repo)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                plan=json.loads((output/'render_plan.json').read_text())
                self.assertEqual(len(plan['samples']),count)
                self.assertEqual({r['split'] for r in plan['samples']},{'test' if preview else 'train'})
                self.assertEqual(set(plan['expected_primary_counts']),{'NONE','FOLD','DENT'})
                self.assertTrue(all(r['sampling_profile']=='eval-gap' for r in plan['samples']))
                self.assertTrue((output/'dataset_request.json').is_file())
                self.assertTrue((output/'all/data.yaml').is_file())
                self.assertFalse((output/'render.log').exists())

    def test_worker_lock_is_independent_and_exclusive(self):
        with fixture() as temp:
            root=Path(temp)
            with exclusive(root):
                with exclusive(root,'.domain-worker.lock'):
                    with self.assertRaises(RuntimeError):
                        with exclusive(root,'.domain-worker.lock'): pass
            with exclusive(root,'.domain-worker.lock'): pass

    def test_committed_hash_and_prefix_reject_corruption(self):
        with fixture() as temp:
            root=Path(temp);folder=root/'all';folder.mkdir()
            f=folder/'sample';f.write_bytes(b'first')
            plan={'samples':[{'sample_id':'one'}]}
            manifest={'samples':[{'sample_id':'one','output_sha256':{'sample':hashlib.sha256(b'first').hexdigest()}}]}
            check_committed(root,plan,manifest)
            f.write_bytes(b'changed')
            with self.assertRaises(ValueError):check_committed(root,plan,manifest)
            manifest['samples'][0]['sample_id']='unexpected'
            with self.assertRaises(ValueError):check_committed(root,plan,manifest,hash_from=1)

    def test_json_replace_is_complete(self):
        import json
        with fixture() as temp:
            path=Path(temp)/'metadata.json'
            atomic_json(path,{'completed':1});atomic_json(path,{'completed':2})
            self.assertEqual(json.loads(path.read_text()),{'completed':2})
            self.assertEqual(list(path.parent.glob('*.tmp')),[])
