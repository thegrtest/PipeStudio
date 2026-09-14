"""Verify committed production samples while the unattended run continues."""
from collections import defaultdict
from pathlib import Path
import json
import sys
from PIL import Image, ImageChops

root = Path(__file__).resolve().parents[1]
folder = Path(json.loads((root/'examples/rolling-shells/dirty-defect-loop/collection.json').read_text())['folder'])
progress = json.loads((folder/'progress.json').read_text())
paths = progress['captures'][:3]
assert len(paths) == 3, 'Wait for the first three complete captures'
samples = [json.loads((folder/path).read_text()) for path in paths]
assert {info['camera_id'] for info in samples} == {'FRONT_45', 'REAR_45', 'OVERHEAD'}
total_masks = total_crops = 0

def check_labels(path, annotations, width, height):
    actual = [[float(v) for v in line.split()] for line in path.read_text().splitlines()]
    expected = []
    for item in annotations:
        if item['bbox_xywh']:
            x, y, w, h = item['bbox_xywh']
            expected.append([item['class_id'], (x+w/2)/width, (y+h/2)/height, w/width, h/height])
    assert len(actual) == len(expected), path
    assert all(len(row) == 5 and all(abs(a-b) < 1e-7 for a, b in zip(row, wanted))
               for row, wanted in zip(actual, expected)), path

for info in samples:
    assert (info['width'], info['height']) == (2400, 1200)
    assert info['render_quality']['samples'] == 192 and info['motion_blur'] is False
    specimens = info['recipe']['items']
    assert {item['normal_appearance']['category'] for item in specimens} == {'clean', 'light', 'heavy'}
    assert all(item['normal_appearance']['label_policy'] == 'normal_not_defect' for item in specimens)
    assert all('dirt' not in item['class_name'] and 'dust' not in item['class_name'] for item in info['annotations'])
    shells = {}; regions = defaultdict(list)
    for key, directory in [('annotations', 'labels'), ('shell_annotations', 'shells/labels'),
                           ('region_annotations', 'regions/labels')]:
        check_labels(folder/directory/(Path(info['image']).stem+'.txt'), info[key], 2400, 1200)
        for annotation in info[key]:
            with Image.open(folder/annotation['mask']) as im: mask = im.convert('L')
            assert mask.size == (2400, 1200)
            hist = mask.histogram(); bounds = mask.getbbox()
            assert sum(hist[1:255]) == 0 and hist[255] == annotation['visible_pixels']
            assert [bounds[0], bounds[1], bounds[2]-bounds[0], bounds[3]-bounds[1]] == annotation['bbox_xywh']
            if key == 'shell_annotations': shells[annotation['flashlight_id']] = mask
            if key == 'region_annotations': regions[annotation['flashlight_id']].append(mask)
            total_masks += 1
    union = Image.new('L', (2400, 1200))
    for shell_id, mask in shells.items():
        assert ImageChops.multiply(union, mask).getbbox() is None
        union = ImageChops.lighter(union, mask)
        region_union = Image.new('L', (2400, 1200))
        for region in regions[shell_id]: region_union = ImageChops.lighter(region_union, region)
        assert ImageChops.difference(mask, region_union).getbbox() is None
    with Image.open(folder/info['image']) as im: source = im.convert('RGB')
    for crop in info['crops']:
        x, y, w, h = crop['source_bbox_xywh']
        with Image.open(folder/crop['image']) as im:
            assert ImageChops.difference(im.convert('RGB'), source.crop((x, y, x+w, y+h))).getbbox() is None
        if crop['region'] == 'flashlight': assert 0 < x and 0 < y and x+w < 2400 and y+h < 1200
        check_labels((folder/crop['image']).with_suffix('.txt'), crop['annotations'], w, h)
        total_crops += 1
report = dict(passed=True, images=3, masks=total_masks, crops=total_crops, all_three_cameras=True,
              dirt_excluded_from_defect_classes=True, mixed_appearance=True, folder=str(folder))
(root/'verification/dirty-collection-start-validation.json').write_text(json.dumps(report, indent=2))
print(json.dumps(report, indent=2))
