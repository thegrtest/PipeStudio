"""Consolidate committed shell captures into independent, verified training sets.

Run with the workspace Python. Rendering is never started by this script.
"""
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json
import math
import random
import shutil
import time
from PIL import Image

ROOT = Path(__file__).resolve().parent
CLASSES = ['plastic_dent', 'metal_dent', 'metal_scratch', 'plastic_scratch',
           'open_center', 'protruding_crimp', 'body_twist']
SPLITS = ('train', 'val', 'test')
RATIOS = (.8, .1, .1)
KINDS = {'frames': '', 'whole_shell': 'crops/whole_shell', 'regions': 'crops/regions'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def pixels(image):
    return hashlib.sha256(str(image.size).encode() + image.tobytes()).hexdigest()


def atomic(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


class Groups:
    def __init__(self): self.parent = []; self.tokens = {}
    def add(self):
        index = len(self.parent); self.parent.append(index); return index
    def find(self, index):
        while self.parent[index] != index:
            self.parent[index] = self.parent[self.parent[index]]; index = self.parent[index]
        return index
    def join(self, left, right):
        left, right = self.find(left), self.find(right)
        if left != right: self.parent[max(left, right)] = min(left, right)
    def link(self, index, token):
        if token in self.tokens: self.join(index, self.tokens[token])
        else: self.tokens[token] = index


def yolo(annotations, width, height):
    rows = []
    for a in annotations:
        x, y, w, h = a['bbox_xywh']
        rows.append(f"{a['class_id']} {(x+w/2)/width:.10f} {(y+h/2)/height:.10f} {w/width:.10f} {h/height:.10f}")
    return '\n'.join(rows)+ ('\n' if rows else '')


def boxes_from_masks(annotations, masks, crop):
    result = []
    for a, mask in zip(annotations, masks):
        section = mask.crop(crop); bounds = section.getbbox()
        if bounds:
            result.append({k: a[k] for k in ('class_id', 'class_name', 'defect_id', 'flashlight_id', 'region')})
            result[-1].update(bbox_xywh=[bounds[0], bounds[1], bounds[2]-bounds[0], bounds[3]-bounds[1]],
                              visible_pixels=section.histogram()[255])
    return result


def build(output, exclude_dirty=False):
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    sources = json.loads((ROOT/'verification/training-source-inventory.json').read_text())
    records = []; frame_metadata = {}; recipes = {}; excluded = []; audit = []
    groups = Groups(); seen = {}; aliases = []; valid_frames = 0

    def add_record(record, image):
        record['pixel_sha256'] = pixels(image)
        record['width'], record['height'] = image.size
        key = (record['kind'], record['pixel_sha256'])
        signature = digest([(a['class_id'], a['bbox_xywh']) for a in record['annotations']])
        if key in seen:
            previous, previous_signature = seen[key]
            if signature != previous_signature:
                raise ValueError('Identical image has conflicting labels: '+record['id'])
            groups.join(record['group_index'], previous['group_index'])
            aliases.append(dict(duplicate=record['id'], retained=previous['id'], source_frame=record['parent_id']))
            return
        seen[key] = record, signature; records.append(record)

    for source_index, inventory in enumerate(sources):
        folder = ROOT/inventory['folder']
        if inventory['classes'] != dict(enumerate(CLASSES)) and inventory['classes'] != {str(i):name for i,name in enumerate(CLASSES)}:
            excluded.append(dict(source=str(folder.relative_to(ROOT)), reason='Different product/class schema (tapered pipes)'))
            continue
        manifest = json.loads((folder/'manifest.json').read_text())
        committed = {item['image'] for item in manifest.get('samples', manifest.get('images', []))}
        del manifest
        if (folder/'progress.json').exists():
            committed_metadata = set(json.loads((folder/'progress.json').read_text())['captures'])
        else: committed_metadata = None
        source_counts = Counter(); source_id = f's{source_index:02d}'
        for metadata_path in sorted((folder/'metadata').glob('*.json')):
            relative_metadata = metadata_path.relative_to(folder).as_posix()
            info = json.loads(metadata_path.read_text())
            if info['image'] not in committed or (committed_metadata is not None and relative_metadata not in committed_metadata):
                excluded.append(dict(source=str(metadata_path.relative_to(ROOT)), reason='Not in completed capture records'))
                continue
            dirty = any(item.get('normal_appearance', {}).get('category') == 'heavy' for item in info['recipe']['items'])
            if exclude_dirty and dirty:
                source_counts['excluded_dirty_frames'] += 1; continue
            parent_id = source_id+'_'+Path(info['image']).stem
            try:
                source_image = folder/info['image']
                with Image.open(source_image) as im: image = im.convert('RGB')
                width, height = image.size
                assert (width, height) == (info['width'], info['height']), 'Image dimensions do not match metadata'
                annotations = []; masks = []
                for a in info['annotations']:
                    if not a['bbox_xywh']: continue
                    assert 0 <= a['class_id'] < len(CLASSES) and CLASSES[a['class_id']] == a['class_name'], 'Class mapping mismatch'
                    with Image.open(folder/a['mask']) as im: mask = im.convert('L')
                    assert mask.size == image.size, 'Mask dimensions do not match'
                    histogram = mask.histogram(); bounds = mask.getbbox()
                    assert not sum(histogram[1:255]) and bounds, 'Invalid binary instance mask'
                    box = [bounds[0], bounds[1], bounds[2]-bounds[0], bounds[3]-bounds[1]]
                    assert box == a['bbox_xywh'] and histogram[255] == a['visible_pixels'], 'Mask and annotation disagree'
                    annotations.append({k:a[k] for k in ('class_id','class_name','defect_id','flashlight_id','region')})
                    annotations[-1].update(bbox_xywh=box, visible_pixels=histogram[255], source_mask=str(folder/a['mask']))
                    masks.append(mask)
            except (OSError, ValueError, AssertionError, KeyError) as exc:
                excluded.append(dict(source=str(metadata_path.relative_to(ROOT)), reason=str(exc)))
                source_counts['invalid_frames'] += 1; continue

            group_index = groups.add()
            for field in ('split_group', 'specimen_group', 'sequence_id'):
                if info.get(field): groups.link(group_index, field+':'+str(info[field]))
            groups.link(group_index, 'specimen_seed:'+str(info['recipe']['seed']))
            for item in info['recipe']['items']:
                identity = {k:v for k,v in item.items() if k not in ('index','x','flip','roll','source_shell',
                    'rolling_index','random_group','normal_appearance')}
                if identity.get('defect'):
                    identity['defect'] = {k:v for k,v in identity['defect'].items() if k not in ('id','flashlight_id')}
                groups.link(group_index, 'specimen:'+digest(identity))
            recipe_key = digest(info['recipe'])
            recipes.setdefault(recipe_key, info['recipe'])
            metadata = {k:info[k] for k in ('camera_id','frame','sequence_id','pass_index','appearance_version',
                'render_quality','parameters','region_mapping','camera','lighting','shell_poses') if k in info}
            metadata.update(source_dataset=str(folder.relative_to(ROOT)), source_metadata=relative_metadata,
                source_image=info['image'], recipe='recipes/'+recipe_key+'.json', heavy_dirt=dirty,
                region_boxes=[{k:v for k,v in a.items() if k!='mask'} for a in info['region_annotations'] if a['bbox_xywh']],
                shell_boxes=[{k:v for k,v in a.items() if k!='mask'} for a in info.get('shell_annotations',[]) if a['bbox_xywh']])
            frame_metadata[parent_id] = metadata
            common = dict(parent_id=parent_id, source_image=str(source_image), source_metadata=str(metadata_path),
                group_index=group_index, source_id=source_id, camera_id=info['camera_id'], heavy_dirt=dirty,
                appearance_version=info.get('appearance_version'), recipe_seed=info['recipe']['seed'])
            add_record(dict(common, id=parent_id, kind='frames', crop=None, annotations=annotations), image)
            source_counts['frames'] += 1; source_counts['positive_frames'] += bool(annotations)
            valid_frames += 1
            # Crops are regenerated from verified RGB. Every defect visible in
            # the rectangular crop gets a label, including neighboring shells.
            for crop in info.get('crops', []):
                x, y, w, h = crop['source_bbox_xywh']; region = crop['region']
                kind = 'whole_shell' if region == 'flashlight' else 'regions'
                if not all(isinstance(v, int) for v in (x,y,w,h)) or min(x,y)<0 or w<1 or h<1 or x+w>width or y+h>height:
                    source_counts['invalid_crop_bounds'] += 1; continue
                if kind == 'whole_shell' and (x==0 or y==0 or x+w==width or y+h==height):
                    source_counts['excluded_edge_shell_crops'] += 1; continue
                if min(w,h)<8:
                    source_counts['excluded_tiny_crops'] += 1; continue
                bounds = (x, y, x+w, y+h)
                crop_annotations = boxes_from_masks(annotations, masks, bounds)
                if kind == 'regions' and not crop_annotations:
                    source_counts['omitted_negative_region_crops'] += 1; continue
                name = parent_id+'__'+region.lower()+f"_{crop['flashlight_id']:02d}"
                add_record(dict(common, id=name, kind=kind, crop=list(bounds), crop_region=region,
                    target_shell=crop['flashlight_id'], annotations=crop_annotations), image.crop(bounds))
                source_counts[kind+'_crops'] += 1
            if valid_frames % 100 == 0:
                status=dict(state='auditing', verified_frames=valid_frames, candidate_images=len(records), elapsed_seconds=round(time.monotonic()-started))
                atomic(output/'build-status.json', status); print(json.dumps(status), flush=True)
        loose_images = [path.name for path in (folder/'images').glob('*.png') if 'images/'+path.name not in committed]
        for filename in loose_images: excluded.append(dict(source=str(folder.relative_to(ROOT))+'/images/'+filename, reason='Image has no committed metadata'))
        audit.append(dict(source_id=source_id, folder=str(folder.relative_to(ROOT)), counts=dict(source_counts),
            source_status=inventory['status'], committed_records=len(committed)))

    assert records and valid_frames
    group_records = defaultdict(list)
    for record in records: group_records[groups.find(record['group_index'])].append(record)
    group_names = {key:'group_'+digest(sorted(r['parent_id'] for r in values))[:16] for key,values in group_records.items()}
    # Balance source-frame counts, defect counts and acquisition domains.
    features = {}; totals = Counter()
    for key, values in group_records.items():
        feature = Counter()
        for r in values:
            if r['kind'] != 'frames': continue
            feature['images'] += 1
            feature['domain:'+r['source_id']] += 1
            for a in r['annotations']: feature['class:'+str(a['class_id'])] += 1
        features[key] = feature; totals.update(feature)
    current = {split:Counter() for split in SPLITS}; assignments = {}
    order = sorted(features, key=lambda key:(-features[key]['images'], digest([42,group_names[key]])))
    for key in order:
        feature = features[key]; scores = []
        for split, ratio in zip(SPLITS, RATIOS):
            score = 0.
            for name, amount in feature.items():
                target = totals[name]*ratio
                weight = 10 if name=='images' else (1.5 if name.startswith('domain:') else 1.)
                before = current[split][name]-target
                score += weight*((before+amount)**2-before**2)/(target+1)
            scores.append(score)
        split = SPLITS[min(range(3), key=lambda i:scores[i])]
        assignments[key] = split; current[split].update(feature)
    for split in SPLITS:
        assert all(current[split]['class:'+str(i)] for i in range(len(CLASSES))), 'A split is missing a defect class'
    for record in records:
        key=groups.find(record.pop('group_index'))
        record['group']=group_names[key]; record['split']=assignments[key]

    atomic(output/'source_inventory.json', audit)
    atomic(output/'exclusions.json', excluded)
    atomic(output/'duplicates.json', aliases)
    (output/'recipes').mkdir()
    for key, recipe in recipes.items(): atomic(output/'recipes'/f'{key}.json',recipe)
    for kind, relative in KINDS.items():
        base=output/relative
        for split in SPLITS:
            (base/'images'/split).mkdir(parents=True,exist_ok=True)
            (base/'labels'/split).mkdir(parents=True,exist_ok=True)
        (base/'annotations').mkdir(exist_ok=True)
        (base/'classes.txt').write_text('\n'.join(CLASSES)+'\n')
        # No machine-specific root. An absolute YAML filename makes the YAML's
        # containing folder the dataset root in Ultralytics.
        (base/'data.yaml').write_text('train: images/train\nval: images/val\ntest: images/test\nnc: 7\nnames:\n'+
            ''.join(f'  {i}: {name}\n' for i,name in enumerate(CLASSES)))
    (output/'metadata').mkdir()
    for split in SPLITS: (output/'instance_masks'/split).mkdir(parents=True)
    counts=defaultdict(Counter)
    class_counts={kind:{split:Counter() for split in SPLITS} for kind in KINDS}
    coco={(kind,split):dict(images=[],annotations=[],categories=[dict(id=i,name=name) for i,name in enumerate(CLASSES)])
          for kind in KINDS for split in SPLITS}
    by_parent=defaultdict(list)
    for record in records: by_parent[record['parent_id']].append(record)
    manifests={kind:(output/relative/'index.jsonl').open('w',encoding='utf-8') for kind,relative in KINDS.items()}
    completed=0
    try:
        for parent_id, children in by_parent.items():
            with Image.open(children[0]['source_image']) as im: image=im.convert('RGB')
            metadata=dict(frame_metadata[parent_id], group=children[0]['group'], split=children[0]['split'])
            atomic(output/'metadata'/f'{parent_id}.json', metadata)
            for record in children:
                kind,split=record['kind'],record['split']; base=output/KINDS[kind]
                image_rel=f"images/{split}/{record['id']}.png"; label_rel=f"labels/{split}/{record['id']}.txt"
                if kind=='frames': shutil.copy2(record['source_image'],base/image_rel)
                else: image.crop(record['crop']).save(base/image_rel,compress_level=3)
                (base/label_rel).write_text(yolo(record['annotations'],record['width'],record['height']))
                output_annotations=[]
                for a in record['annotations']:
                    output_a={k:v for k,v in a.items() if k!='source_mask'}
                    if kind=='frames':
                        mask_rel=f"instance_masks/{split}/{record['id']}_{a['defect_id']:03d}.png"
                        shutil.copy2(a['source_mask'],output/mask_rel); output_a['mask']=mask_rel
                    output_annotations.append(output_a)
                entry={k:v for k,v in record.items() if k not in ('source_image','source_metadata','annotations')}
                entry.update(image=image_rel,label=label_rel,annotations=output_annotations)
                manifests[kind].write(json.dumps(entry,separators=(',',':'))+'\n')
                dataset=coco[kind,split]; image_id=len(dataset['images'])+1
                dataset['images'].append(dict(id=image_id,file_name=image_rel,width=record['width'],height=record['height'],
                    group=record['group'],source_frame=parent_id,camera_id=record['camera_id']))
                for a in output_annotations:
                    dataset['annotations'].append(dict(id=len(dataset['annotations'])+1,image_id=image_id,
                        category_id=a['class_id'],bbox=a['bbox_xywh'],area=a['visible_pixels'],iscrowd=0))
                    class_counts[kind][split][a['class_name']]+=1
                counts[kind][split]+=1; counts[kind]['positive' if output_annotations else 'negative']+=1
            completed+=1
            if completed%100==0:
                status=dict(state='packaging',completed_frames=completed,total_frames=len(by_parent),
                    written_images=sum(c['positive']+c['negative'] for c in counts.values()),elapsed_seconds=round(time.monotonic()-started))
                atomic(output/'build-status.json',status);print(json.dumps(status),flush=True)
    finally:
        for handle in manifests.values():handle.close()
    for (kind,split),data in coco.items():atomic(output/KINDS[kind]/'annotations'/f'instances_{split}.json',data)
    group_manifest=[dict(group=group_names[key],split=assignments[key],source_frames=features[key]['images']) for key in features]
    atomic(output/'split_groups.json',group_manifest)
    summary=dict(state='packaged',classes=CLASSES,counts={k:dict(v) for k,v in counts.items()},
        class_counts={k:{s:dict(c) for s,c in splits.items()} for k,splits in class_counts.items()},
        groups=len(features),group_counts=dict(Counter(assignments.values())),duplicate_images_removed=len(aliases),
        excluded_records=len(excluded),include_heavily_dirty=not exclude_dirty,elapsed_seconds=round(time.monotonic()-started))
    atomic(output/'summary.json',summary)
    readme=f'''# Shell defect training dataset

Generation was stopped before this folder was built. All files needed for training are inside this folder; source exports are unchanged.

Start with **data.yaml** for the full camera images. There are {counts['frames']['positive']} defect-positive images and {counts['frames']['negative']} verified negative images with empty label files.

- `crops/whole_shell/data.yaml`: complete-shell crops, including clean negative examples. Crops touching a source image edge are excluded.
- `crops/regions/data.yaml`: recorded surface crops containing visible defects. These include partial views and are an optional ROI detector set.
- Each dataset has `images/train`, `images/val`, `images/test` and matching `labels/` directories. Labels use YOLO detection format: class, normalized center x/y, width, height.
- Each dataset also has COCO bounding-box annotations in `annotations/instances_*.json`. COCO filenames are relative to that dataset's root.
- Full-frame binary defect masks are in `instance_masks/`. `index.jsonl` links images, labels, masks, provenance, acquisition details and split groups. `metadata/` preserves camera settings and region/shell boxes; `recipes/` preserves the specimen recipes.

Pass the **absolute path** to the desired `data.yaml` to your trainer. YAML files omit a machine-specific root so the folder can be moved. No training has been started.

Class IDs are unchanged across all sets: {', '.join(f'{i}={name}' for i,name in enumerate(CLASSES))}.

Splits target 80% train, 10% validation and 10% test. Whole populations, all cameras/frames, dirt variants, duplicate images and every derived crop stay in the same split. Physical specimen fingerprints and seed identities link related sources. Actual counts differ slightly because groups are indivisible. All seven classes occur in each full-frame split.

All completed shell export runs are included{' except heavily dirty captures' if exclude_dirty else ', including the earlier heavily dirty run'}. Dirt, dust and normal finish are never labeled as defects. Render generations and resolutions differ; acquisition details and source IDs are retained for filtering. Tapered pipes use a different class schema and are excluded.

RGB files were checked against metadata. Visible defect masks were checked pixel-for-pixel against their boxes and areas. YOLO labels were regenerated from these verified annotations. Crop pixels are regenerated losslessly from verified source RGB and recorded bounds; crop labels include **every visible defect in the rectangle**, including neighboring shells. Negative region-only crops and crops smaller than eight pixels on an axis are omitted. Orphan/incomplete files are listed in `exclusions.json`. Exact duplicate images with matching labels are removed and recorded in `duplicates.json`.

`summary.json` contains image and class counts. `validation.json` is the independent output validation report. Use the same population split across these related datasets; do not randomly re-split individual images or crops.
'''
    (output/'README.md').write_text(readme,encoding='utf-8')
    atomic(output/'build-status.json',summary)
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,default=ROOT/'datasets/Shell_Defects_Training_20260913')
    parser.add_argument('--exclude-dirty',action='store_true')
    args=parser.parse_args();build(args.output,args.exclude_dirty)
