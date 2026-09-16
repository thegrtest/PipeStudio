"""Build official OIDN 2.4.1 for baseline ARM64 without replacing system files."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

user = Path.home()
cache = user/'.cache/pipestudio'
deps = user/'opt/pipestudio-build-deps'
cache.mkdir(parents=True, exist_ok=True)
deps.mkdir(parents=True, exist_ok=True)
packages = [
    ('oidn-2.4.1.src.tar.gz',
     'https://github.com/RenderKit/oidn/releases/download/v2.4.1/oidn-2.4.1.src.tar.gz',
     '9c7c77ae0d57e004479cddb7aaafd405c2cc745153bed4805413c21be610e17b'),
    ('ispc-v1.29.1-linux.aarch64.tar.gz',
     'https://github.com/ispc/ispc/releases/download/v1.29.1/ispc-v1.29.1-linux.aarch64.tar.gz',
     'f4353abfd58f40c06bf984e268bdb1adf750a349e52b97e9f82494adb8033bf7'),
]
for name, url, expected in packages:
    archive = cache/name
    if not archive.exists(): urllib.request.urlretrieve(url, archive)
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): digest.update(block)
    if digest.hexdigest() != expected: raise ValueError('Download checksum mismatch: '+name)
    with tarfile.open(archive) as package:
        for member in package:
            dest = (deps/member.name).resolve()
            if not dest.is_relative_to(deps) or dest == deps: raise ValueError('Unsafe archive path')
            if member.issym() or member.islnk():
                link = ((dest.parent if member.issym() else deps)/member.linkname).resolve()
                if not link.is_relative_to(deps): raise ValueError('Unsafe archive link')
            elif not (member.isfile() or member.isdir()): raise ValueError('Unexpected archive member')
            package.extract(member, deps, **({'filter':'data'} if hasattr(tarfile,'data_filter') else {}))
    print('Verified package:', name, flush=True)
source = deps/'oidn-2.4.1'
if not source.exists():
    matches = list(deps.glob('oidn*'))
    source = next(p for p in matches if (p/'CMakeLists.txt').exists())
ispc = next(deps.glob('ispc*/bin/ispc'))
venv = user/'PipeStudio/.venv/bin'
build = cache/'oidn-build'
prefix = user/'opt/oidn-pipestudio'
command = [str(venv/'cmake'), '-S', str(source), '-B', str(build), '-G', 'Ninja',
    '-DCMAKE_MAKE_PROGRAM='+str(venv/'ninja'), '-DCMAKE_BUILD_TYPE=Release',
    '-DCMAKE_INSTALL_PREFIX='+str(prefix), '-DCMAKE_C_FLAGS=-march=armv8-a',
    '-DCMAKE_CXX_FLAGS=-march=armv8-a', '-DISPC_EXECUTABLE='+str(ispc),
    '-DISPC_FLAGS_RELEASE=-O3 --cpu=cortex-a57', '-DOIDN_DEVICE_CPU=ON',
    '-DOIDN_DEVICE_CUDA=OFF', '-DOIDN_DEVICE_SYCL=OFF', '-DOIDN_DEVICE_HIP=OFF',
    '-DOIDN_APPS=OFF', '-DOIDN_INSTALL_DEPENDENCIES=OFF']
subprocess.run(command, check=True)
subprocess.run([str(venv/'cmake'), '--build', str(build), '--parallel', '6'], check=True)
subprocess.run([str(venv/'cmake'), '--install', str(build)], check=True)
(cache/'oidn-build.json').write_text(json.dumps(dict(version='2.4.1',
    prefix=str(prefix), cpu_target='cortex-a57', gpu_device=False,
    packages=[dict(name=n,url=u,sha256=h) for n,u,h in packages]), indent=2))
print('AGX_DENOISER_BUILT', prefix, flush=True)
