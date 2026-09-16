"""Install the verified private runtime under the current user's home directory."""
import hashlib
from pathlib import Path
import tarfile

archive = Path.home()/'.cache/pipestudio/blender-arm-runtime.tar.gz'
expected = 'f4be7e5a5bb3105ab181c618db2322a966dfee37d2d2f86dae6c2470692c111d'
digest = hashlib.sha256()
with archive.open('rb') as stream:
    for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
if digest.hexdigest() != expected:
    raise ValueError('Runtime transfer checksum mismatch')
target = (Path.home()/'opt/pipestudio-arm').resolve()
target.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive) as package:
    for member in package:
        path = (target/member.name).resolve()
        if not path.is_relative_to(target) or path == target or not (member.isfile() or member.isdir()):
            raise ValueError('Unsafe runtime archive member')
        package.extract(member, target, **({'filter':'data'} if hasattr(tarfile,'data_filter') else {}))
print('Verified and installed private runtime:', target, flush=True)
