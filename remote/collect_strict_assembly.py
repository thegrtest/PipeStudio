"""Copy committed strict assembly pairs into an existing images/labels folder.

Live workers are read only. A frozen metadata snapshot and source checksums
exclude unfinished and rejected renders. Existing destination files never change.
"""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shlex

from PIL import Image

from fleet import ROOT,run
from fleet_common import read_json,write_json,digest_file,inside,safe_name
from fleet_node import lock
from collect_fleet import copy_node
from collect_assembly_defects import label_rows,copy_checked


INVENTORY=r'''
import json,sys,re
from datetime import datetime,timezone
from pathlib import Path
root=Path(sys.argv[1]);job=sys.argv[2];folder=root/'jobs'/job
plan=json.loads((folder/'plan.json').read_text())
if not plan['settings'].get('strict_visibility'):raise ValueError('Not a strict assembly run')
planned={r['sample_id']:r for r in plan['rows']};records=[]
# Metadata is atomically published only after the complete pair is written.
paths=sorted((folder/'metadata').glob('*.json'))
for path in paths:
    data=json.loads(path.read_text());sid=data['sample_id']
    if not re.fullmatch(r'assembly_\d+_f\d+',sid) or path.stem!=sid or sid not in planned:
        raise ValueError('Unexpected assembly ID')
    qa=data.get('visibility_quality',{})
    if qa.get('passed') is not True or qa.get('version')!=planned[sid]['recipe']['quality_profile']:
        raise ValueError('Missing strict approval: '+sid)
    if data['hidden_defects'] or len(qa['instances'])!=len(data['annotations']):
        raise ValueError('Incomplete visibility checks: '+sid)
    for entry,annotation in zip(qa['instances'],data['annotations']):
        if (entry['passed'] is not True or entry['screen']['passed'] is not True or
            entry['counterfactual']['passed'] is not True or
            entry['instance_id']!=annotation['instance_id'] or
            entry['specimen_id']!=annotation['specimen_id']):raise ValueError('Unapproved defect: '+sid)
    if (folder/'rejections'/(sid+'.json')).exists():raise ValueError('Accepted/rejected conflict: '+sid)
    if data['image']!='all/images/'+sid+'.png':raise ValueError('Unexpected image path')
    if qa['beauty_sha256']!=data['sha256'][data['image']]:raise ValueError('QA image differs')
    files={}
    for kind,relative in [('image',data['image']),('label','all/labels/'+sid+'.txt')]:
        source=folder/relative;digest=data['sha256'][relative]
        if not source.is_file() or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Invalid committed pair')
        files[kind]=dict(relative=f'jobs/{job}/'+relative,sha256=digest,bytes=source.stat().st_size)
    if (data['width'],data['height'])!=(1920,1200):raise ValueError('Unexpected resolution')
    records.append(dict(sample_id=sid,split_group=data['split_group'],width=data['width'],height=data['height'],
        look=data['recipe']['look'],condition=data['recipe']['condition'],annotations=data['annotations'],
        visibility_quality=qa,files=files))
print(json.dumps(dict(job=job,captured_at=datetime.now(timezone.utc).isoformat(),records=records,
                     rejected_at_snapshot=len(list((folder/'rejections').glob('*.json'))))))
'''


def inventory(node,job):
    job=safe_name(job)
    command=[node['python'],'-c',INVENTORY,node['root'],job]
    if node['transport']!='local':command=['ssh','-o','BatchMode=yes',node['alias'],shlex.join(command)]
    return json.loads(run(command,timeout=90))


def collect(run_folders,output,class_id):
    output=Path(output).resolve()
    if not (output/'images').is_dir() or not (output/'labels').is_dir():
        raise ValueError('Destination must already contain images and labels folders')
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    archive=ROOT/'exports/assembly_imports'/stamp;archive.mkdir(parents=True)
    sources={}
    for run_folder in run_folders:
        config=read_json(Path(run_folder)/'fleet.json')
        if config['pipeline']!='assembly':raise ValueError('Not an assembly fleet run')
        for name,node in config['nodes'].items():
            key=name+'_'+safe_name(config['job'])
            sources[key]=dict(node=node,job=config['job'],run=str(run_folder))
    with lock(archive.parent/'import.lock'):
        # Freeze both inventories before transferring any file.
        with ThreadPoolExecutor(max_workers=len(sources)) as pool:
            futures={k:pool.submit(inventory,s['node'],s['job']) for k,s in sources.items()}
            snapshots={k:f.result() for k,f in futures.items()}
        write_json(archive/'inventory.json',snapshots)
        write_json(archive/'request.json',dict(output=str(output),source_class_map={i:class_id for i in range(4)},sources=sources))
        original={str(p.relative_to(output)):digest_file(p) for folder in ('images','labels')
                  for p in (output/folder).rglob('*') if p.is_file()}
        write_json(archive/'existing_hashes.json',original)
        transfers={};records={}
        for key,snapshot in snapshots.items():
            stage=archive/key;(stage/'.collection').mkdir(parents=True)
            files={}
            for row in snapshot['records']:
                sid=row['sample_id']
                if sid in records:raise ValueError('Duplicate sample across runs: '+sid)
                records[sid]=(key,row)
                for kind,info in row['files'].items():
                    files[info['relative']]={**info,'target':f'{kind}/{sid}'+('.png' if kind=='image' else '.txt')}
            transfers[key]=files
        print(json.dumps(dict(snapshot_pairs={k:len(v['records']) for k,v in snapshots.items()},
                              total_pairs=len(records))),flush=True)
        with ThreadPoolExecutor(max_workers=len(sources)) as pool:
            futures={k:pool.submit(copy_node,k,s['node'],transfers[k],archive/k) for k,s in sources.items()}
            copied={k:f.result() for k,f in futures.items()}
        write_json(archive/'transfer.json',copied)
        prepared=[];classes=Counter();clean=0
        # Validate every pair and every collision before changing the dataset.
        for sid,(key,row) in records.items():
            stage=archive/key;image=stage/'image'/(sid+'.png');raw=stage/'label'/(sid+'.txt')
            assert digest_file(image)==row['files']['image']['sha256']
            assert digest_file(raw)==row['files']['label']['sha256']
            with Image.open(image) as im:
                if im.size!=(1920,1200):raise ValueError('Wrong image size: '+sid)
                im.verify()
            labels=label_rows(raw.read_text(encoding='utf-8-sig'),range(4))
            if len(labels)!=len(row['annotations']):raise ValueError('Label count mismatch: '+sid)
            for line,ann in zip(labels,row['annotations']):
                if int(line[0])!=ann['class_id']:raise ValueError('Source class mismatch')
                x,y,w,h=ann['bbox_xywh'];expected=((x+w/2)/1920,(y+h/2)/1200,w/1920,h/1200)
                if any(abs(float(v)-e)>1e-7 for v,e in zip(line[1:],expected)):raise ValueError('Source box mismatch')
            converted=''.join(str(class_id)+' '+' '.join(line[1:])+'\n' for line in labels)
            target_image=output/'images'/(sid+'.png');target_label=output/'labels'/(sid+'.txt')
            for old in (output/'images').glob(sid+'.*'):
                if old!=target_image:raise ValueError('Conflicting image extension: '+str(old))
            label_hash=hashlib.sha256(converted.encode()).hexdigest()
            for path,digest in ((target_image,row['files']['image']['sha256']),(target_label,label_hash)):
                if path.exists() and digest_file(path)!=digest:raise ValueError('Existing pair conflicts: '+str(path))
            mapped=stage/'mapped_labels'/(sid+'.txt');mapped.parent.mkdir(exist_ok=True)
            mapped.write_bytes(converted.encode())
            prepared.append(dict(sample_id=sid,source=key,image=str(image),mapped_label=str(mapped),
                image_sha256=row['files']['image']['sha256'],label_sha256=label_hash,
                image_existed=target_image.exists(),label_existed=target_label.exists(),instances=len(labels)))
            classes.update(int(line[0]) for line in labels);clean+=not labels
        write_json(archive/'validated_plan.json',prepared)
        for item in prepared:
            sid=item['sample_id']
            copy_checked(Path(item['mapped_label']),output/'labels'/(sid+'.txt'),item['label_sha256'])
            copy_checked(Path(item['image']),output/'images'/(sid+'.png'),item['image_sha256'])
        for relative,expected in original.items():
            if digest_file(inside(output,relative))!=expected:raise ValueError('Existing destination file changed: '+relative)
        for item in prepared:
            for folder,suffix,key in (('images','.png','image_sha256'),('labels','.txt','label_sha256')):
                if digest_file(output/folder/(item['sample_id']+suffix))!=item[key]:raise ValueError('Final pair mismatch')
        result=dict(output=str(output),snapshot_pairs=len(prepared),new_images=sum(not r['image_existed'] for r in prepared),
            new_labels=sum(not r['label_existed'] for r in prepared),empty_control_labels=clean,
            defect_boxes=sum(classes.values()),source_class_counts=dict(classes),destination_class_id=class_id,
            dimensions=[1920,1200],existing_files_unchanged=len(original),tracking_labels_copied=0,
            source_counts={k:len(v['records']) for k,v in snapshots.items()},
            completed_at=datetime.now(timezone.utc).isoformat(),verified=True,receipt=str(archive/'receipt.json'))
        write_json(archive/'receipt.json',result)
        return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,action='append',required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--single-class',type=int,required=True)
    args=p.parse_args()
    if args.single_class<0:raise ValueError('Class ID must be nonnegative')
    print(json.dumps(collect(args.run,args.output,args.single_class),indent=2))
