"""Independent verification of the finished, portable training folder."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import math
import sys
from PIL import Image, ImageChops

root=Path(__file__).resolve().parents[1]
folder=Path(sys.argv[1]) if len(sys.argv)>1 else root/'datasets/Shell_Defects_Training_20260913'
assert not (folder/'masks').exists(), 'Do not trigger automatic semantic dataset selection'
classes=['plastic_dent','metal_dent','metal_scratch','plastic_scratch','open_center','protruding_crimp','body_twist']
kinds={'frames':'','whole_shell':'crops/whole_shell','regions':'crops/regions'}
splits=('train','val','test')
indexes={kind:[json.loads(line) for line in (folder/relative/'index.jsonl').read_text().splitlines()]
         for kind,relative in kinds.items()}
frames={row['id']:row for row in indexes['frames']}
aliases={row['duplicate']:row['retained'] for row in json.loads((folder/'duplicates.json').read_text())}
group_splits={}; hash_splits={}; report={}; sample_sheets=[]

def load_rgb(path):
    with Image.open(path) as im: return im.convert('RGB')

for kind,relative in kinds.items():
    base=folder/relative; rows=indexes[kind]; counters=Counter(); class_counts=defaultdict(Counter)
    assert (base/'classes.txt').read_text().splitlines()==classes
    config=(base/'data.yaml').read_text()
    assert all(f'{split}: images/{split}' in config for split in splits)
    assert 'path:' not in config, 'Dataset config contains a machine-specific root'
    by_parent=defaultdict(list)
    for row in rows: by_parent[row['parent_id']].append(row)
    completed=0
    for parent_id, children in by_parent.items():
        original_id=aliases.get(parent_id,parent_id)
        original=load_rgb(folder/frames[original_id]['image'])
        parent_masks=[]
        if kind!='frames':
            for a in frames[original_id]['annotations']:
                with Image.open(folder/a['mask']) as im: parent_masks.append((a,im.convert('L')))
        for row in children:
            image=load_rgb(base/row['image'])
            assert image.size==(row['width'],row['height'])
            fingerprint=hashlib.sha256(str(image.size).encode()+image.tobytes()).hexdigest()
            assert fingerprint==row['pixel_sha256'], 'Saved pixel mismatch: '+row['id']
            group=row['group']; split=row['split']
            assert group_splits.setdefault(group,split)==split, 'Population leakage between splits'
            assert hash_splits.setdefault(fingerprint,split)==split, 'Identical pixels leaked between splits'
            actual=[[float(v) for v in line.split()] for line in (base/row['label']).read_text().splitlines()]
            assert len(actual)==len(row['annotations'])
            for values,a in zip(actual,row['annotations']):
                assert len(values)==5 and all(math.isfinite(v) for v in values)
                assert int(values[0])==values[0] and 0<=values[0]<7
                x,y,w,h=a['bbox_xywh']; width,height=image.size
                assert 0<=x<x+w<=width and 0<=y<y+h<=height and w>0 and h>0
                expected=[a['class_id'],(x+w/2)/width,(y+h/2)/height,w/width,h/height]
                assert all(abs(a-b)<1e-8 for a,b in zip(values,expected)), row['id']
                class_counts[split][classes[a['class_id']]]+=1
                if kind=='frames':
                    with Image.open(folder/a['mask']) as im: mask=im.convert('L')
                    assert mask.size==image.size
                    hist=mask.histogram(); bounds=mask.getbbox()
                    assert hist[255]==a['visible_pixels'] and not sum(hist[1:255])
                    assert [bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]]==a['bbox_xywh']
                    counters['verified_instance_masks']+=1
            if row['crop']:
                assert ImageChops.difference(image,original.crop(row['crop'])).getbbox() is None
                if kind=='whole_shell':
                    x0,y0,x1,y1=row['crop']
                    assert 0<x0<x1<original.width and 0<y0<y1<original.height
                # Reconstruct ALL crop labels independently from packaged parent masks.
                reconstructed=[]
                for a,parent_mask in parent_masks:
                    mask=parent_mask.crop(row['crop'])
                    bounds=mask.getbbox()
                    if bounds: reconstructed.append((a['class_id'],[bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]]))
                assert reconstructed==[(a['class_id'],a['bbox_xywh']) for a in row['annotations']], 'Crop omits visible defects'
            counters[split]+=1; counters['positive' if row['annotations'] else 'negative']+=1
            completed+=1
        if completed and completed%1000<len(children):
            print(json.dumps(dict(state='validating',dataset=kind,verified=completed,total=len(rows))),flush=True)
    for split in splits:
        assert len(list((base/'images'/split).glob('*.png')))==counters[split]
        assert len(list((base/'labels'/split).glob('*.txt')))==counters[split]
        coco=json.loads((base/'annotations'/f'instances_{split}.json').read_text())
        assert [c['name'] for c in coco['categories']]==classes
        assert len(coco['images'])==counters[split]
        assert len(coco['annotations'])==sum(class_counts[split].values())
        known={im['id']:im for im in coco['images']}
        assert len(known)==len(coco['images'])
        indexed={row['image']:row for row in rows if row['split']==split}
        actual_boxes=defaultdict(list)
        for a in coco['annotations']:
            assert a['image_id'] in known and 0<=a['category_id']<7 and a['area']>0
            actual_boxes[a['image_id']].append((a['category_id'],a['bbox']))
        for image_id,entry in known.items():
            assert entry['file_name'] in indexed
            expected=indexed[entry['file_name']]
            assert (entry['width'],entry['height'])==(expected['width'],expected['height'])
            assert actual_boxes[image_id]==[(a['class_id'],a['bbox_xywh']) for a in expected['annotations']]
        if kind=='frames':assert all(class_counts[split][name]>0 for name in classes)
    report[kind]=dict(images=len(rows),counts=dict(counters),class_counts={s:dict(c) for s,c in class_counts.items()})

result=dict(passed=True,datasets=report,groups=len(group_splits),group_leakage=False,duplicate_pixel_leakage=False,
    all_images_decoded=True,all_label_boxes_verified=True,all_crops_pixel_exact=True,
    crop_labels_include_all_visible_defects=True,all_full_frame_classes_in_each_split=True)
(folder/'validation.json').write_text(json.dumps(result,indent=2))
(folder/'build-status.json').write_text(json.dumps(dict(state='ready',images=sum(len(rows) for rows in indexes.values()),validated=True),indent=2))
print(json.dumps(result,indent=2),flush=True)
