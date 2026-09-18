"""Archive soap/stain pairs, preserving mixed annotations and verifying before removal."""
import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime,timezone
import json
from pathlib import Path
import shutil
import os
import uuid

from PIL import Image

from collect_fleet import checked_labels
from fleet_common import digest_file,digest_json,inside,read_json,write_json
from fleet_node import lock


def verified_copy(source,target,expected):
    if target.exists():
        if digest_file(target)!=expected: raise ValueError('Archive file conflicts: '+str(target))
        return
    target.parent.mkdir(parents=True,exist_ok=True)
    temporary=target.with_name(target.name+'.'+uuid.uuid4().hex+'.partial')
    try:
        shutil.copyfile(source,temporary)
        if digest_file(temporary)!=expected: raise ValueError('Archive checksum failed: '+str(target))
        os.replace(temporary,target)
    finally: temporary.unlink(missing_ok=True)


def metadata(folder,receipt,selection=None):
    classes={k:v for k,v in receipt['classes'].items() if int(k) not in receipt.get('excluded_class_ids',[])}
    rows=receipt['samples']
    names={r['name'] for r in rows}
    if any({p.stem for p in (folder/subdir).glob('*.'+ext)}!=names for subdir,ext in (('images','png'),('labels','txt'))):
        raise ValueError('Dataset image/label pairs differ: '+str(folder))
    (folder/'classes.txt').write_text('\n'.join(classes.values())+'\n',encoding='utf-8')
    (folder/'data.yaml').write_text('path: '+json.dumps(folder.as_posix())+'\ntrain: images\nnames:\n'+
                                  ''.join(f'  {k}: {json.dumps(v)}\n' for k,v in classes.items()),encoding='utf-8')
    result=dict(valid=True,images=len(rows),labels=len(rows),output=str(folder),selection_class_id=selection,
                bytes=sum(f['bytes'] for r in rows for f in r['files'].values()),
                primary_counts=dict(Counter(r['primary_kind'] for r in rows)),
                class_image_counts=dict(Counter(c for r in rows for c in r['class_ids'])),
                completed_at=datetime.now(timezone.utc).isoformat(),excluded_class_ids=receipt.get('excluded_class_ids',[]))
    write_json(folder/'collection.json',result)
    return result


def split(source,soap,stain):
    source,soap,stain=(p.resolve() for p in (source,soap,stain))
    roots=(source,soap,stain)
    if any(a==b or a.is_relative_to(b) or b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]):
        raise ValueError('Datasets must be separate, nonnested directories')
    journal_path=source/'.collection/surface-split.json'
    journal=read_json(journal_path)
    destinations={2:soap,3:stain}
    target_names={str(k):str(v) for k,v in destinations.items()}
    if journal:
        if journal['destinations']!=target_names: raise ValueError('Existing split has different destinations')
        original=journal['original_receipt']
    else:
        original=read_json(source/'.collection/receipt.json')
        if not original: raise ValueError('Expected a verified fleet collection receipt')
        if original['classes']!={'0':'Fold','1':'Dent','2':'Soap stain','3':'Oil stain'}:
            raise ValueError('Unexpected class mapping')
        for row in original['samples']:
            for kind,subdir,ext in (('image','images','png'),('label','labels','txt')):
                info=row['files'][kind]
                if info['target']!=f"{subdir}/{row['name']}.{ext}": raise ValueError('Unexpected target path')
                path=inside(source,info['target'])
                if digest_file(path)!=info['sha256']: raise ValueError('Source checksum differs: '+str(path))
            label=inside(source,row['files']['label']['target'])
            checked_labels(label,row,{0,1,2,3})
            row['class_ids']=sorted({int(line.split()[0]) for line in label.read_text().splitlines() if line.strip()})
        expected={r['name'] for r in original['samples']}
        for subdir,ext in (('images','png'),('labels','txt')):
            if {p.stem for p in (source/subdir).glob('*.'+ext)}!=expected:
                raise ValueError('Source files differ from collection receipt')
        journal=dict(source=str(source),destinations=target_names,original_receipt=original,phase='copying')
        write_json(journal_path,journal)
    signature=dict(source=str(source),receipt_sha256=digest_json(original))
    archive_receipts={}; counts={}
    for class_id,destination in destinations.items():
        marker=destination/'.collection/split-source.json'
        if destination.exists() and any(destination.iterdir()) and read_json(marker)!=signature:
            raise ValueError('Archive destination contains unrelated files: '+str(destination))
        destination.mkdir(parents=True,exist_ok=True)
        (destination/'images').mkdir(exist_ok=True);(destination/'labels').mkdir(exist_ok=True)
        write_json(marker,signature)
        rows=[r for r in original['samples'] if class_id in r['class_ids']]
        for number,row in enumerate(rows,1):
            for info in row['files'].values():
                verified_copy(inside(source,info['target']),inside(destination,info['target']),info['sha256'])
            if number%200==0: print(json.dumps(dict(dataset=destination.name,copied=number,total=len(rows))),flush=True)
        receipt={**deepcopy(original),'samples':deepcopy(rows),'selection_class_id':class_id,
                 'excluded_class_ids':[],'archive_note':'All original annotations retained, including other classes.'}
        archive_receipts[class_id]=receipt
    # Verify both complete archives before removing any source image or label.
    for class_id,receipt in archive_receipts.items():
        destination=destinations[class_id]
        for row in receipt['samples']:
            for info in row['files'].values():
                if digest_file(inside(destination,info['target']))!=info['sha256']: raise ValueError('Archive changed')
            with Image.open(inside(destination,row['files']['image']['target'])) as image:
                if image.size!=(row['width'],row['height']): raise ValueError('Archive dimensions differ')
                image.verify()
            checked_labels(inside(destination,row['files']['label']['target']),row,{0,1,2,3})
        write_json(destination/'.collection/receipt.json',receipt)
        counts[class_id]=metadata(destination,receipt,class_id)
        (destination/'README.txt').write_text(
            'Selected from '+str(source)+' by '+original['classes'][str(class_id)]+'.\n'
            'Full original labels are preserved: 0 Fold, 1 Dent, 2 Soap stain, 3 Oil stain.\n'
            'Images containing both soap and oil stains appear in both archives. Keep these duplicates in the same training split.\n',encoding='utf-8')
    journal['phase']='archives_verified';write_json(journal_path,journal)
    retained=[r for r in original['samples'] if not {2,3}.intersection(r['class_ids'])]
    receipt={**original,'samples':retained,'excluded_class_ids':[2,3],'archived_datasets':target_names}
    write_json(source/'.collection/receipt.json',receipt)
    for row in original['samples']:
        if not {2,3}.intersection(row['class_ids']): continue
        # Exact, resolved paths only; no recursive deletion. Verified copies exist in the archives.
        for info in row['files'].values():
            path=inside(source,info['target'])
            if path.exists():
                if digest_file(path)!=info['sha256']: raise ValueError('Source changed before removal')
                path.unlink()
    counts['retained']=metadata(source,receipt)
    journal.update(phase='complete',counts={str(k):v['images'] for k,v in counts.items()})
    write_json(journal_path,journal)
    print(json.dumps(dict(source=str(source),destinations=target_names,counts=journal['counts']),indent=2),flush=True)
    return counts


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--soap',type=Path,required=True)
    parser.add_argument('--stain',type=Path,required=True)
    args=parser.parse_args()
    with lock(args.source.resolve().parent/('.'+args.source.name+'.collection.lock')):
        split(args.source,args.soap,args.stain)
