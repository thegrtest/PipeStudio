"""Exercise real process failure/recovery and exclusive-lock behavior without rendering."""
from pathlib import Path
import json,sys,uuid
from contextlib import nullcontext
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import rolling_supervisor as supervisor
test_folder=root/'verification'/('supervisor-test-'+uuid.uuid4().hex[:8])
test_folder.mkdir()
with nullcontext(str(test_folder)) as directory:
    folder=Path(directory)
    supervisor.write(folder/'job.json',{})
    lock=supervisor.acquire(folder)
    assert lock and supervisor.is_active(folder)
    assert supervisor.acquire(folder) is None
    lock.close();assert not supervisor.is_active(folder)
    worker=folder/'worker.py'
    worker.write_text('''import json,sys
from pathlib import Path
folder=Path(sys.argv[1]);attempt=int(sys.argv[2])
if attempt==1:sys.exit(7)
state='checkpoint' if attempt==2 else 'complete'
(folder/'status.json').write_text(json.dumps(dict(state=state,attempted=attempt-1,saved=attempt-1)))
''')
    factory=lambda attempt:[sys.executable,str(worker),str(folder),str(attempt)]
    assert supervisor.supervise(folder,'unused',command_factory=factory,backoffs=(0,))==0
    result=supervisor.read(folder/'supervisor.json')
    assert result['workers_started']==3 and result['restarts']==1 and result['state']=='complete'
    assert not supervisor.is_active(folder)
    (folder/'status.json').unlink()
    assert supervisor.supervise(folder,'unused',command_factory=lambda n:[sys.executable,'-c','raise SystemExit(9)'],backoffs=(0,))==1
    assert supervisor.read(folder/'supervisor.json')['workers_started']==3
    assert supervisor.read(folder/'status.json')['state']=='failed'
out=dict(passed=True,recovery_after_process_exit=True,worker_recycling=True,duplicate_supervisor_blocked=True,bounded_failures=True)
(root/'verification/rolling-supervisor-validation.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
