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
