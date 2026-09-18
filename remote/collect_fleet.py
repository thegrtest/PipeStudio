"""Collect a live fleet snapshot without stopping or updating any render worker."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import uuid

from PIL import Image

from fleet import ROOT, run, parallel
from fleet_common import digest_file,read_json,write_json
from fleet_node import lock


def command(node):
    helper=(Path(__file__).parent/'fleet_export.py').read_text(encoding='utf-8')
    args=[node['python'],'-c',helper,node['root']]
    return args if node['transport']=='local' else ['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',node['alias'],shlex.join(args)]


def inventory(node, job=None):
    return json.loads(run(command(node),input=json.dumps(dict(action='inventory',job=job)).encode(),timeout=60))


def checked_labels(path, row, class_ids):
    lines=[line.split() for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if len(lines)!=row['instances']: raise ValueError('Label instance count differs from committed record')
    for line in lines:
        if len(line)!=5 or int(line[0]) not in class_ids: raise ValueError('Invalid YOLO class or row')
        x,y,w,h=map(float,line[1:])
        if not all(math.isfinite(v) for v in (x,y,w,h)) or not (0<=x<=1 and 0<=y<=1 and 0<w<=1 and 0<h<=1):
            raise ValueError('Invalid normalized bounding box')
        if min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6:
            raise ValueError('Bounding box leaves image')


def copy_node(name,node,files,destination):
    if not files: return dict(files=0,bytes=0)
    error_path=destination/'.collection'/f'{name}-transfer.log'
    total=0; count=0
    with error_path.open('wb') as errors:
        process=subprocess.Popen(command(node),stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=errors,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            process.stdin.write(json.dumps(dict(action='stream',files=list(files))).encode())
            process.stdin.close()
            with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
                seen=set()
                for member in archive:
                    if not member.isfile() or member.name not in files or member.name in seen:
                        raise ValueError('Unexpected transfer member')
                    receipt=files[member.name]; target=destination/receipt['target']
                    if member.size!=receipt['bytes']: raise ValueError('Transfer size differs from snapshot')
                    target.parent.mkdir(parents=True,exist_ok=True)
                    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
                    digest=hashlib.sha256()
                    try:
                        with archive.extractfile(member) as source, temporary.open('xb') as output:
                            while data:=source.read(1024*1024):
                                digest.update(data); output.write(data); total+=len(data)
                        if digest.hexdigest()!=receipt['sha256']: raise ValueError('Transferred file checksum mismatch')
                        if target.exists():
                            if digest_file(target)!=receipt['sha256']: raise ValueError('Destination file conflicts with collection')
                            temporary.unlink()
                        else: os.replace(temporary,target)
                    except Exception:
                        temporary.unlink(missing_ok=True)
                        raise
                    count+=1; seen.add(member.name)
                    if count%100==0: print(json.dumps(dict(device=name,files_copied=count,files_planned=len(files))),flush=True)
                if seen!=set(files): raise ValueError('Transfer ended before all requested files arrived')
            if process.wait(timeout=30): raise RuntimeError('Export failed; see '+str(error_path))
        finally:
            if process.poll() is None: process.kill(); process.wait()
            process.stdout.close()
    return dict(files=count,bytes=total)


def collect(config, output, job=None):
    output=output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    with lock(output.parent/('.'+output.name+'.collection.lock')):
        pending=read_json(output/'.collection/surface-split.json',{})
        if pending and pending.get('phase')!='complete': raise RuntimeError('Finish the pending dataset split before collecting')
        return _collect(config,output,job)


def _collect(config, output, job=None):
    nodes=read_json(config)['nodes']; output=output.resolve()
    snapshots=parallel(nodes,lambda name,node:inventory(node,job))
    if any('error' in result for result in snapshots.values()): raise RuntimeError(json.dumps(snapshots))
    mappings=[s['classes'] for s in snapshots.values() if s['classes'] is not None]
    if not mappings or any(mapping!=mappings[0] for mapping in mappings): raise ValueError('No images or inconsistent class mappings')
    classes=mappings[0]
    if output.exists() and any(output.iterdir()) and not (output/'.collection/receipt.json').exists():
        raise ValueError('Destination contains unrelated files; refusing to mix or overwrite them')
    output.mkdir(parents=True,exist_ok=True); (output/'.collection').mkdir(exist_ok=True)
    existing=read_json(output/'.collection/receipt.json',{})
    excluded=set(existing.get('excluded_class_ids',[]))
    if existing and existing['classes']!=classes: raise ValueError('Existing collection has different class names')
    pairs={}; names={}; image_labels={}
    for row in existing.get('samples',[]):
        if excluded.intersection(row.get('class_ids',[])): raise ValueError('Existing collection still contains excluded classes')
        key=(row['files']['image']['sha256'],row['files']['label']['sha256'])
        pairs[key]=row; names[row['name']]=key
    for name,snapshot in snapshots.items():
        for sample in snapshot['samples']:
            if excluded.intersection(sample['class_ids']): continue
            key=(sample['files']['image']['sha256'],sample['files']['label']['sha256'])
            if key[0] in image_labels and image_labels[key[0]]!=key[1]:
                raise ValueError('Identical images have conflicting labels')
            image_labels[key[0]]=key[1]
            origin=dict(node=name,job=sample['job'],sample_id=sample['sample_id'])
            if key in pairs:
                if origin not in pairs[key]['origins']: pairs[key]['origins'].append(origin)
                continue
            stem=sample['sample_id']
            if stem in names and names[stem]!=key:
                stem+='_'+hashlib.sha256(''.join(key).encode()).hexdigest()[:16]
            if stem in names: raise ValueError('Cannot assign a unique destination name')
            names[stem]=key
            pairs[key]={**sample,'node':name,'name':stem,'origins':[origin]}
    transfers={name:{} for name in nodes}
    for sample in pairs.values():
        for kind,subdir,ext in (('image','images','png'),('label','labels','txt')):
            info=sample['files'][kind]; relative=f"{subdir}/{sample['name']}.{ext}"
            info['target']=relative; target=output/relative
            if target.exists():
                if digest_file(target)!=info['sha256']: raise ValueError('Existing collection file differs: '+relative)
            else: transfers[sample['node']][info['relative']]={**info,'target':relative}
    receipt=dict(classes=classes,samples=list(pairs.values()),job_filter=job,excluded_class_ids=sorted(excluded),
                 archived_datasets=existing.get('archived_datasets',{}),captured_at=datetime.now(timezone.utc).isoformat(),
                 snapshots={name:{k:s[k] for k in ('captured_at','jobs')} for name,s in snapshots.items()})
    write_json(output/'.collection/receipt.json',receipt)
    print(json.dumps(dict(snapshot_images={n:len(s['samples']) for n,s in snapshots.items()},unique_pairs=len(pairs),
                          files_to_copy=sum(len(f) for f in transfers.values()))),flush=True)
    results=parallel(nodes,lambda name,node:copy_node(name,node,transfers[name],output))
    write_json(output/'.collection/transfers.json',results)
    if any('error' in result for result in results.values()): raise RuntimeError(json.dumps(results))
    counts=Counter(); total_bytes=0
    for row in pairs.values():
        for kind in ('image','label'):
            file=output/row['files'][kind]['target']
            if digest_file(file)!=row['files'][kind]['sha256']: raise ValueError('Final checksum failed: '+str(file))
            total_bytes+=file.stat().st_size
        with Image.open(output/row['files']['image']['target']) as image:
            if image.size!=(row['width'],row['height']): raise ValueError('Image dimensions differ from manifest')
            image.verify()
        checked_labels(output/row['files']['label']['target'],row,{int(k) for k in classes})
        counts[row['primary_kind']]+=1
    expected={row['name'] for row in pairs.values()}
    if {p.stem for p in (output/'images').glob('*.png')}!=expected or {p.stem for p in (output/'labels').glob('*.txt')}!=expected:
        raise ValueError('Image and label sets differ')
    active_classes={k:v for k,v in classes.items() if int(k) not in excluded}
    (output/'classes.txt').write_text('\n'.join(active_classes.values())+'\n',encoding='utf-8')
    (output/'data.yaml').write_text('path: '+json.dumps(output.as_posix())+'\ntrain: images\nnames:\n'+
        ''.join(f'  {k}: {json.dumps(v)}\n' for k,v in active_classes.items()),encoding='utf-8')
    result=dict(valid=True,images=len(pairs),labels=len(pairs),job_filter=job,bytes=total_bytes,primary_counts=dict(counts),
                completed_at=datetime.now(timezone.utc).isoformat(),output=str(output),transfer=results)
    write_json(output/'collection.json',result)
    print(json.dumps(result,indent=2),flush=True)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'fleet_nodes.local.json')
    parser.add_argument('--job',help='Collect only this saved production cycle; default includes all committed fleet jobs')
    args=parser.parse_args()
    collect(args.config,args.output,args.job)
