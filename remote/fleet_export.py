"""Read-only inventory and streaming export of committed fleet image/label pairs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tarfile
import time


def source_path(root, relative):
    parts=relative.split('/')
    if (len(parts)!=5 or parts[0]!='jobs' or parts[2]!='all' or
            not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',parts[1]) or
            parts[3] not in ('images','labels') or
            not re.fullmatch(r'[a-zA-Z0-9_-]+\.'+('png' if parts[3]=='images' else 'txt'),parts[4])):
        raise ValueError('Export is limited to fleet images and labels')
    path=(root/relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Export file is missing or outside the fleet directory')
    return path


def inventory(root, job_filter=None):
    rows=[]; jobs=[]; classes=None
    if job_filter is not None and not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',job_filter):
        raise ValueError('Invalid fleet job filter')
    manifests=sorted((root/'jobs').glob('*/all/manifest.json'),reverse=True)
    if job_filter is not None:
        manifests=[path for path in manifests if path.parents[1].name==job_filter]
    for manifest_path in manifests:
        for attempt in range(8):
            try:
                raw=manifest_path.read_bytes(); manifest=json.loads(raw)
                break
            except (PermissionError,json.JSONDecodeError):
                if attempt==7: raise
                time.sleep(.1)
        records=manifest.get('samples',[])
        if not records: continue
        if classes is not None and classes!=manifest['classes']:
            raise ValueError('Fleet jobs have incompatible class mappings')
        classes=manifest['classes']; job=manifest_path.parents[1].name
        jobs.append(dict(job=job,committed=len(records),manifest_sha256=hashlib.sha256(raw).hexdigest()))
        for row in records:
            sid=row['sample_id']
            image=row['image']; label='labels/'+sid+'.txt'
            if image!='images/'+sid+'.png': raise ValueError('Unexpected image naming')
            files={}
            for kind,relative in (('image',image),('label',label)):
                expected=row['output_sha256'][relative]
                if not re.fullmatch('[a-f0-9]{64}',expected): raise ValueError('Invalid committed checksum')
                rel=f'jobs/{job}/all/{relative}'
                files[kind]=dict(relative=rel,sha256=expected,bytes=source_path(root,rel).stat().st_size)
            rows.append(dict(sample_id=sid,job=job,files=files,primary_kind=row['primary_kind'],
                             width=row['width'],height=row['height'],instances=len(row['instances']),
                             setup=row['setup']))
    return dict(captured_at=datetime.now(timezone.utc).isoformat(),classes=classes,jobs=jobs,samples=rows)


def stream(root, request, output):
    # Yield CPU to the render process; stream directly without a remote archive.
    if hasattr(os,'nice'): os.nice(10)
    with tarfile.open(fileobj=output,mode='w|') as archive:
        for relative in request['files']:
            source=source_path(root,relative)
            info=archive.gettarinfo(str(source),arcname=relative)
            if not info.isfile(): raise ValueError('Expected a regular generated file')
            with source.open('rb') as handle: archive.addfile(info,handle)


if __name__=='__main__':
    root=Path(sys.argv[1]).resolve(); request=json.load(sys.stdin)
    if request['action']=='inventory': print(json.dumps(inventory(root,request.get('job'))))
    elif request['action']=='stream': stream(root,request,sys.stdout.buffer)
    else: raise ValueError('Unknown read-only export operation')
