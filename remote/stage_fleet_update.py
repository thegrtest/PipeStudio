"""Install an immutable renderer snapshot without changing active generation."""
import json
from pathlib import Path
import sys

from release_store import stage,install
from fleet_node import lock


if __name__=='__main__':
    root=Path(sys.argv[1]).resolve(); request=json.load(sys.stdin)
    request['activate']=False
    with lock(root/'update-stage.lock'):
        result=(stage if request['action']=='offer' else install)(root,request)
    print(json.dumps(result))
