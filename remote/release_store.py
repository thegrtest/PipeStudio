"""Verified incremental deployment into immutable, per-run renderer directories."""
import hashlib
import os
from pathlib import Path
import re
import shutil
import tarfile
import time
import uuid

from fleet_common import digest_file, digest_json, inside, read_json, safe_name, write_json


def checked_manifest(root, release, files):
    safe_name(release)
    if not isinstance(files, dict) or not files or digest_json(files) != release:
        raise ValueError('Release does not match its file manifest')
    for name, digest in files.items():
        inside(root, name)
        if name == 'release.json' or not re.fullmatch(r'[a-f0-9]{64}', digest):
            raise ValueError('Invalid release manifest entry')
    return files


def verify(root, release, files):
    folder = root/'releases'/release
    return (read_json(folder/'release.json', {}).get('files') == files and
            all(inside(folder,n).is_file() and digest_file(inside(folder,n)) == h for n,h in files.items()))


def stage(root, request):
    release = request['release']; files = checked_manifest(root,release,request['files'])
    if verify(root, release, files):
        if request.get('activate',True): write_json(root/'current_release.json', {'release':release})
        return dict(installed=True, release=release, missing=[], base_release=release)
    prior = read_json(root/'current_release.json', {}).get('release')
    if not prior:
        candidates = list((root/'releases').glob('*/release.json'))
        if candidates: prior = max(candidates,key=lambda p:p.stat().st_mtime).parent.name
    base = root/'releases'/safe_name(prior) if prior else None
    previous = read_json(base/'release.json', {}).get('files', {}) if base else {}
    missing = []
    for name, digest in files.items():
        if (previous.get(name) != digest or not inside(base,name).is_file() or
                digest_file(inside(base,name)) != digest):
            missing.append(name)
    return dict(installed=False,release=release,missing=missing,base_release=prior)


def install(root, request):
    release = request['release']; files = checked_manifest(root,release,request['files'])
    if verify(root,release,files):
        if request.get('activate',True): write_json(root/'current_release.json', {'release':release})
        return dict(installed=release,reused=len(files),changed=0)
    archive_name = request['archive']
    if not archive_name.endswith('.tgz'): raise ValueError('Expected .tgz patch')
    safe_name(archive_name[:-4])
    archive = root/'incoming'/archive_name
    if digest_file(archive) != request['sha256']: raise ValueError('Patch transfer hash mismatch')
    target = root/'releases'/release
    if target.exists(): raise ValueError('Existing release is damaged; refusing to alter an immutable snapshot')
    # Avoid duplicating the long release hash in temporary paths on Windows.
    scratch = root/'releases'/('.stage-'+uuid.uuid4().hex)
    scratch.mkdir(parents=True)
    changed = set()
    with tarfile.open(archive) as package:
        for member in package:
            if not member.isfile() or member.name not in files or member.name in changed:
                raise ValueError('Unexpected source patch member')
            data = package.extractfile(member).read()
            if hashlib.sha256(data).hexdigest() != files[member.name]:
                raise ValueError('Patch file checksum mismatch: '+member.name)
            dest = inside(scratch,member.name); dest.parent.mkdir(parents=True,exist_ok=True)
            dest.write_bytes(data); changed.add(member.name)
    base_id = request.get('base_release')
    base = root/'releases'/safe_name(base_id) if base_id else None
    for name, digest in files.items():
        if name in changed: continue
        if base is None: raise ValueError('Patch is missing a required file')
        source = inside(base,name)
        if not source.is_file() or digest_file(source) != digest:
            raise ValueError('Base release changed: '+name)
        dest=inside(scratch,name); dest.parent.mkdir(parents=True,exist_ok=True)
        # Separate files keep corruption or manual edits in one release isolated.
        shutil.copyfile(source,dest)
    if any(digest_file(inside(scratch,n))!=h for n,h in files.items()):
        raise ValueError('Staged release changed before activation')
    write_json(scratch/'release.json',dict(release=release,files=files))
    # Windows indexing/sync software can briefly hold a newly written file.
    # Keep activation atomic and retry only transient access/sharing failures.
    for attempt in range(8):
        try:
            os.rename(scratch,target)
            break
        except PermissionError as error:
            if getattr(error,'winerror',None) not in (5,32,33) or attempt==7 or target.exists():
                raise
            time.sleep(min(.1*2**attempt,1))
    if request.get('activate',True): write_json(root/'current_release.json', {'release':release})
    return dict(installed=release,reused=len(files)-len(changed),changed=len(changed))
