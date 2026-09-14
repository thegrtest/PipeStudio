"""Independent image/label/crop and specimen-split checks for the pilot export."""
from pathlib import Path
import sys,json,hashlib
from collections import Counter
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from flashlight_lab.dataset_review import review
from verification.verify_flashlight_crops import verify

folder=Path(sys.argv[1]).resolve()
manifest=json.loads((folder/'manifest.json').read_text());infos=manifest['images']
assert len(infos)==72
groups={};visible={'train':Counter(),'val':Counter()};hashes={}
for info in infos:
    group=info['specimen_group'];split=info['split']
    entry=groups.setdefault(group,dict(split=split,cameras=set(),recipe=info['recipe']))
    assert entry['split']==split and entry['recipe']==info['recipe']
    assert info['camera_id'] not in entry['cameras'];entry['cameras'].add(info['camera_id'])
    assert split in ('train','val')
    digest=hashlib.sha256((folder/info['image']).read_bytes()).hexdigest()
    if digest in hashes:assert hashes[digest]==split,'Duplicate image crosses splits'
    hashes[digest]=split
    visible[split].update(a['class_id'] for a in info['annotations'] if a['visible_pixels'])
assert len(groups)==24
assert all(g['cameras']=={'FRONT_45','REAR_45','OVERHEAD'} for g in groups.values())
assert all(set(counts)==set(range(7)) for counts in visible.values())
for target in (folder,folder/'regions'):
    for split in ('train','val'):
        lines=(target/f'{split}.txt').read_text().splitlines()
        assert len(lines)==sum(info['split']==split for info in infos)
        assert all((target/line).exists() for line in lines)
review(folder);review(folder,regions=True);verify(folder)
for source in ('annotations.coco.json','regions.review.coco.json'):
    coco=json.loads((folder/source).read_text())
    for split in ('train','val'):
        images=[image for image in coco['images'] if image['split']==split]
        ids={image['id'] for image in images}
        data={**coco,'images':images,'annotations':[a for a in coco['annotations'] if a['image_id'] in ids]}
        (folder/f'{Path(source).stem}.{split}.json').write_text(json.dumps(data,indent=2))
summary=dict(passed=True,rows=24,images=72,train_images=48,validation_images=24,
    clean_images=sum(not i['annotations'] for i in infos),classes=manifest['classes'],
    visible_class_counts=visible,specimen_views_kept_together=True,duplicate_split_leakage=False)
(folder/'dataset-validation.json').write_text(json.dumps(summary,indent=2))
(folder/'README.md').write_text('''# Shell defect pilot

72 Blender/Cycles images at 1024 × 512 pixels: 24 independently seeded rows, each seen by two opposing 45° cameras and one overhead camera. There are 48 training images and 24 validation images. Every row stays entirely within one split. Both splits include all seven defect classes and clean examples.

## Training files

- `dataset.yaml`: YOLO defect dataset; `images/`, `labels/`, binary `masks/`.
- `regions/dataset.yaml`: separate YOLO dataset for top, body, Brass Face and Plastic Face.
- `annotations.coco.train.json`, `annotations.coco.val.json`: defect COCO splits.
- `regions.review.coco.train.json`, `regions.review.coco.val.json`: region COCO splits.
- `metadata/`: camera matrices, full exterior recipes, severity parameters and specimen IDs.
- `crops/` and `crops.json`: exact source-pixel specimen/region crops and translated boxes.
- `review/index.html`, `region-review/index.html`: labeled review galleries.
- `dataset-validation.json`: validation result and visible class counts.

Defect IDs: 0 plastic_dent, 1 metal_dent, 2 metal_scratch, 3 plastic_scratch, 4 open_center, 5 protruding_crimp, 6 body_twist. Dust and worn printing are normal appearance. Twist masks identify the sheared body band; the rigidly rotated plastic end retains its region label without receiving a twist defect label.

Each non-clean row has a defective majority. Three severity variants anchor each defect family, with additional mixed defects on the other shells. Dents include shallow through deeper deformations; twist examples span +8°, −35° and +105°. Clean rows carry empty defect labels and populated region labels.

This is a pilot for checking visual realism and the training pipeline, not a measured performance benchmark. Shapes are controlled exterior approximations rather than calibrated material simulations. Assess trained models on separate real inspection images; do not treat this synthetic validation split as evidence of real-world accuracy.

To make larger independent batches, use Inspection Studio → Mixed row → All three cameras → Batch. The row count produces three images per row. Keep the resulting specimen groups together when splitting the larger export. The reproducible pilot generator is `flashlight_lab/generate_defect_pilot.py` in the workspace and supports `--output`, `--resolution` and `--samples` when run with Blender.
''',encoding='utf-8')
print(json.dumps(summary))
