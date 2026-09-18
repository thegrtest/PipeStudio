"""Collect stopped assembly jobs into Conveyor with defect-only YOLO pairs."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import sys

from PIL import Image

from fleet import ROOT, node_call, parallel, run
from fleet_common import read_json, write_json, digest_file, inside
from collect_fleet import copy_node
from fleet_node import lock

CLASS_MAP = {0: 0, 3: 1}
CLASS_NAMES = ['Dent', 'Fold']
IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp'}

# The same read-only inventory runs on each source machine. Its committed
# metadata names the defect label file separately from the tracking label file.
INVENTORY = r'''
import json,sys
from pathlib import Path
folder=Path(sys.argv[1]);prefix=sys.argv[2]
plan=json.loads((folder/'plan.json').read_text())
planned={r['sample_id']:r for r in plan['rows']}
records=[]
for path in sorted((folder/'metadata').glob('*.json')):
    data=json.loads(path.read_text());sid=data['sample_id']
    if sid not in planned or path.stem!=sid:raise ValueError('Unplanned metadata')
    if data['image']!='all/images/'+sid+'.png':raise ValueError('Invalid image path')
    annotations=data['annotations']
    if any(a['class_id'] not in (0,3) for a in annotations):raise ValueError('Unexpected assembly defect class')
    files={}
    for kind,rel in [('image',data['image']),('label','all/labels/'+sid+'.txt')]:
        source=folder/rel
        if not source.is_file():raise ValueError('Missing committed pair: '+rel)
        files[kind]=dict(relative=prefix+rel,sha256=data['sha256'][rel],bytes=source.stat().st_size)
    records.append(dict(sample_id=sid,split_group=data['split_group'],width=data['width'],height=data['height'],
        condition=data['recipe']['condition'],look=data['recipe']['look'],instances=len(annotations),
        class_ids=sorted({a['class_id'] for a in annotations}),files=files))
if set(r['sample_id'] for r in records)!=set(r['sample_id'] for r in plan['rows'][:len(records)]):
    raise ValueError('Committed metadata is not a prefix of the saved plan')
print(json.dumps(dict(source=str(folder),samples=records)))
'''


def inventory(node, job):
    source = node['root'].replace('\\', '/') + '/jobs/' + job
    arguments = [node['python'], '-c', INVENTORY, source, f'jobs/{job}/']
    command = arguments if node['transport'] == 'local' else ['ssh', '-o', 'BatchMode=yes', node['alias'], shlex.join(arguments)]
    return json.loads(run(command, timeout=90))


def local_inventory(folder):
    return json.loads(run([sys.executable, '-c', INVENTORY, str(folder), ''], timeout=90))


def label_rows(text, allowed):
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        if len(parts) != 5 or parts[0] not in {str(c) for c in allowed}:
            raise ValueError('Invalid class ID or YOLO box')
        x, y, w, h = map(float, parts[1:])
        if not all(math.isfinite(v) for v in (x, y, w, h)) or min(w, h) <= 0:
            raise ValueError('Non-finite or empty box')
        if min(x-w/2, y-h/2) < -1e-6 or max(x+w/2, y+h/2) > 1+1e-6:
            raise ValueError('Box outside the image')
        rows.append(parts)
    return rows


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.pending')
    temporary.write_text(text, encoding='utf-8')
    os.replace(temporary, path)


def copy_checked(source, target, expected, hardlink=False):
    if target.exists():
        if digest_file(target) != expected:
            raise ValueError('Existing destination differs: ' + str(target))
        return
    if digest_file(source) != expected:
        raise ValueError('Source checksum changed: ' + str(source))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.partial')
    if hardlink:
        try:
            os.link(source, temporary)
        except OSError:
            shutil.copyfile(source, temporary)
    else:
        shutil.copyfile(source, temporary)
    if digest_file(temporary) != expected:
        raise ValueError('Copied checksum differs: ' + str(target))
    os.replace(temporary, target)


def collect(run_folder, output, earlier):
    settings = read_json(run_folder / 'fleet.json')
    if settings.get('pipeline') != 'assembly':
        raise ValueError('Expected an assembly fleet run')
    nodes = settings['nodes']
    states = parallel(nodes, lambda name, node: node_call(node, dict(action='status', job=settings['job'])))
    if any(s.get('error') or s.get('running') for s in states.values()):
        raise RuntimeError('All selected generation workers must be stopped: ' + json.dumps(states))
    output = output.resolve(); audit = output / '.collection'; audit.mkdir(parents=True, exist_ok=True)
    with lock(audit / 'collection.lock'):
        snapshots = parallel(nodes, lambda name, node: inventory(node, settings['job']))
        if any('error' in s for s in snapshots.values()):
            raise RuntimeError(json.dumps(snapshots))
        for name, snap in snapshots.items():
            if len(snap['samples']) != states[name]['completed']:
                raise ValueError('Node count differs from stopped state: ' + name)
        for index, folder in enumerate(earlier):
            status = read_json(folder / 'status.json')
            if status.get('state') != 'complete':
                raise ValueError('Earlier local batch must be complete')
            snapshots[f'earlier_{index}'] = local_inventory(folder)
        write_json(audit / 'assembly-source-inventory.json', snapshots)
        write_json(audit / 'stopped-workers.json', states)

        # Preserve existing real pairs and unlabeled captures. Record their
        # original hashes once, before importing generated examples.
        original_path = audit / 'original-conveyor.json'
        if not original_path.exists():
            originals = []
            for image in sorted((output / 'all/images').iterdir()):
                if image.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                label = output / 'all/labels' / (image.stem + '.txt')
                originals.append(dict(image=image.relative_to(output).as_posix(), image_sha256=digest_file(image),
                                      label=label.relative_to(output).as_posix() if label.exists() else None,
                                      label_sha256=digest_file(label) if label.exists() else None))
            write_json(original_path, originals)
            if (output / 'data.yaml').exists():
                shutil.copy2(output / 'data.yaml', audit / 'data.before.yaml')
        originals = read_json(original_path)
        records = {}; pairs = {}; collisions = {}; image_labels = {}
        for origin, snapshot in snapshots.items():
            for row in snapshot['samples']:
                key = (row['files']['image']['sha256'], row['files']['label']['sha256'])
                if key[0] in image_labels and image_labels[key[0]] != key[1]:
                    raise ValueError('Identical generated RGB has conflicting annotations')
                image_labels[key[0]] = key[1]
                if key in pairs:
                    records[pairs[key]]['origins'].append(origin)
                    continue
                stem = row['sample_id']
                if stem in collisions and collisions[stem] != key:
                    stem += '_' + key[0][:12]
                if stem in records:
                    raise ValueError('Unresolved generated filename conflict')
                collisions[stem] = key; pairs[key] = stem
                record = {**row, 'name': stem, 'origin': origin, 'origins': [origin]}
                record['files'] = {kind: {**info, 'target': (f'all/images/{stem}.png' if kind == 'image' else f'.collection/source_labels/{stem}.txt')}
                                   for kind, info in row['files'].items()}
                records[stem] = record
        write_json(audit / 'assembly-import-plan.json', dict(run=str(run_folder), mapping=CLASS_MAP, samples=list(records.values())))
        transfers = {name: {} for name in nodes}
        for row in records.values():
            if row['origin'] not in nodes:
                continue
            for info in row['files'].values():
                target = inside(output, info['target'])
                if target.exists():
                    if digest_file(target) != info['sha256']:
                        raise ValueError('Existing import target differs: ' + str(target))
                else:
                    transfers[row['origin']][info['relative']] = info
        print(json.dumps(dict(source_counts={name: len(s['samples']) for name, s in snapshots.items()},
                              unique_generated_pairs=len(records), transfer_files=sum(map(len, transfers.values())))), flush=True)
        copied = parallel(nodes, lambda name, node: copy_node(name, node, transfers[name], output))
        write_json(audit / 'assembly-transfer-results.json', copied)
        if any('error' in s for s in copied.values()):
            raise RuntimeError(json.dumps(copied))
        for row in records.values():
            if row['origin'] in nodes:
                continue
            source = Path(snapshots[row['origin']]['source'])
            for info in row['files'].values():
                copy_checked(inside(source, info['relative']), inside(output, info['target']), info['sha256'])

        examples = []; instances = Counter(); negatives = 0
        for index, row in enumerate(records.values()):
            image = inside(output, row['files']['image']['target'])
            raw = inside(output, row['files']['label']['target'])
            if digest_file(image) != row['files']['image']['sha256'] or digest_file(raw) != row['files']['label']['sha256']:
                raise ValueError('Transferred pair failed final checksum')
            with Image.open(image) as im:
                if im.size != (row['width'], row['height']):
                    raise ValueError('Image dimensions differ from source record')
                im.verify()
            labels = label_rows(raw.read_text(encoding='utf-8-sig'), CLASS_MAP)
            if len(labels) != row['instances']:
                raise ValueError('Defect instance count differs from metadata')
            converted = ''.join(str(CLASS_MAP[int(line[0])]) + ' ' + ' '.join(line[1:]) + '\n' for line in labels)
            target = output / 'all/labels' / (row['name'] + '.txt')
            if target.exists() and target.read_text(encoding='utf-8') != converted:
                raise ValueError('Existing defect label conflicts with import: ' + str(target))
            write_text(target, converted)
            negatives += not labels
            instances.update(CLASS_MAP[int(line[0])] for line in labels)
            examples.append(dict(name=row['name'], image=image.relative_to(output).as_posix(), label=target.relative_to(output).as_posix(),
                                 image_sha256=row['files']['image']['sha256'], label_sha256=digest_file(target),
                                 group=row['split_group'], source='generated'))
            if (index+1) % 500 == 0:
                print(json.dumps(dict(pairs_validated=index+1, total=len(records))), flush=True)
        original_labeled = 0; unlabeled = []
        for row in originals:
            if digest_file(output / row['image']) != row['image_sha256']:
                raise ValueError('Existing camera image changed during collection')
            if not row['label']:
                unlabeled.append(row['image']); continue
            label = output / row['label']
            if digest_file(label) != row['label_sha256']:
                raise ValueError('Existing camera annotation changed during collection')
            labels = label_rows(label.read_text(encoding='utf-8-sig'), (0,))
            instances.update(int(line[0]) for line in labels)
            original_labeled += 1
            examples.append(dict(name=Path(row['image']).stem, image=row['image'], label=row['label'],
                                 image_sha256=row['image_sha256'], label_sha256=row['label_sha256'],
                                 group='existing-camera-capture', source='real'))

        # Keep every rolled view of a generated specimen in one split. All
        # existing labeled real captures stay together in validation.
        groups = sorted({r['group'] for r in examples if r['source']=='generated'},
                        key=lambda g: hashlib.sha256(('conveyor:'+g).encode()).hexdigest())
        validation_groups = set(groups[:max(1, round(len(groups)*.2))]) | {'existing-camera-capture'}
        split_names = {'train': set(), 'val': set()}; split_groups = {'train': set(), 'val': set()}
        for index, row in enumerate(examples):
            split = 'val' if row['group'] in validation_groups else 'train'
            image = output / row['image']; label = output / row['label']
            copy_checked(image, output / split / 'images' / image.name, row['image_sha256'], hardlink=True)
            copy_checked(label, output / split / 'labels' / label.name, row['label_sha256'])
            split_names[split].add(image.stem); split_groups[split].add(row['group']); row['split']=split
            if (index+1) % 500 == 0:print(json.dumps(dict(split_pairs_ready=index+1,total=len(examples))),flush=True)
        if split_groups['train'] & split_groups['val']:
            raise ValueError('Specimen sequence leaks between splits')
        for split, names in split_names.items():
            actual_images = {p.stem for p in (output/split/'images').iterdir() if p.suffix.lower() in IMAGE_SUFFIXES}
            actual_labels = {p.stem for p in (output/split/'labels').glob('*.txt')}
            if actual_images != names or actual_labels != names:
                raise ValueError('Existing split contains unexpected images or labels: ' + split)
        write_text(output / 'classes.txt', '\n'.join(CLASS_NAMES)+'\n')
        write_text(output / 'all/classes.txt', '\n'.join(CLASS_NAMES)+'\n')
        write_text(output / 'data.yaml', 'path: '+json.dumps(output.as_posix())+'\ntask: detection\ntrain: train/images\nval: val/images\nnc: 2\nnames:\n  - Dent\n  - Fold\n')
        write_text(output / 'unlabeled_images.txt', ''.join(p+'\n' for p in unlabeled))
        write_json(audit / 'assembly-import-receipt.json', dict(class_names=CLASS_NAMES, mapping=CLASS_MAP, examples=examples,
                                                              sources={n:len(s['samples']) for n,s in snapshots.items()}))
        result = dict(valid=True, generated_images=len(records), generated_labels=len(records),
                      existing_labeled_real=original_labeled, existing_unlabeled_excluded=len(unlabeled),
                      total_all_images=len(records)+len(originals), total_labeled_pairs=len(examples),
                      split_images={k:len(v) for k,v in split_names.items()}, defect_instances=dict(instances),
                      generated_negative_images=negatives, tracking_labels_copied=0,
                      completed_at=datetime.now(timezone.utc).isoformat())
        write_json(output/'collection.json',result)
        print(json.dumps(result,indent=2),flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--earlier',type=Path,action='append',default=[])
    args=parser.parse_args()
    collect(args.run or Path(read_json(ROOT/'.cache/assembly-fleet-active.json')['folder']),args.output,args.earlier)
