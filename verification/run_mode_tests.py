"""Run regression tests with workspace-owned temporary directories on Windows."""
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
temporary_root=(root/'verification'/'test-temp').resolve()
temporary_root.mkdir(exist_ok=True)

def workspace_temp(suffix=None,prefix=None,dir=None):
    # Python 3.12's private Windows 0700 ACL excludes this sandbox's restricted token.
    # Use the workspace's inherited ACL; only test scratch data is stored here.
    path=(temporary_root/((prefix or 'test_')+uuid.uuid4().hex+(suffix or ''))).resolve()
    assert path.is_relative_to(temporary_root)
    path.mkdir()
    return str(path)

tempfile.mkdtemp=workspace_temp
unittest.main(module=None,argv=['unittest','test_product_modes','test_app_model','test_geometry',
    'test_generation_plan','test_brass_finishes','test_dataset_tools','test_mixed_dataset'])
