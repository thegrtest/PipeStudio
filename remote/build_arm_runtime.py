"""Package the tested Spark renderer with its userspace libraries for ARM nodes.

The system loader is invoked explicitly on the target; this never replaces the
target OS's libc, CUDA toolkit, NVIDIA driver, or other installed libraries.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess
import tarfile

source=Path.home()/'opt/blender-pipestudio/cmake-make'
output=Path.home()/'.cache/pipestudio/blender-arm-runtime.tar.gz'
environment={**os.environ,'LD_LIBRARY_PATH':str(source/'libExt')}
libraries={}
targets=[source/'bin/blender']+list((source/'libExt').glob('*'))+list((source/'bin/5.1').rglob('*.so'))
for target in targets:
    if not target.is_file(): continue
    result=subprocess.run(['ldd',str(target)],env=environment,capture_output=True,text=True)
    for line in result.stdout.splitlines():
        match=re.search(r'^\s*(\S+) => (/\S+)',line)
        if match: name,path=match.groups()
        else:
            match=re.search(r'^\s*(/\S+)',line)
            if not match: continue
            path=match.group(1);name=Path(path).name
        path=Path(path)
        if path.is_relative_to(source) or '/nvidia/' in str(path): continue
        if path.is_file(): libraries[name]=path
loader=Path('/lib/ld-linux-aarch64.so.1')
libraries[loader.name]=loader
temporary=output.with_suffix('.tmp')
with tarfile.open(temporary,'w:gz',compresslevel=1,dereference=True) as bundle:
    bundle.add(source/'bin/blender',arcname='bin/blender')
    bundle.add(source/'bin/5.1',arcname='bin/5.1')
    bundle.add(source/'libExt',arcname='libExt')
    for name,path in sorted(libraries.items()): bundle.add(path,arcname='syslib/'+name)
os.replace(temporary,output)
with output.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
result=dict(archive=str(output),sha256=digest,bytes=output.stat().st_size,system_libraries=len(libraries),
            source_build='CoconutMacaroon/blender-arm64 v10-5.1',blender='5.1.0',driver_included=False)
output.with_suffix('.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result),flush=True)
