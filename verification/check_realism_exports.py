"""Pixel-level invariants for normal finish changes and camera exports."""
from pathlib import Path
import json
from PIL import Image,ImageChops
root=Path(__file__).resolve().parents[1]/'examples/realism-refinement'
count=0
for subdir in ('masks','region_masks'):
    for before in (root/'before'/subdir).glob('*.png'):
        after=root/'finish-only'/subdir/before.name
        with Image.open(before) as a,Image.open(after) as b:
            assert ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None,before
        count+=1
for subdir in ('before','finish-only','after','final'):
    infos=json.loads((root/subdir/'manifest.json').read_text())['samples']
    for info in infos:
        assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in info['recipe']['defects'])==4
for subdir in ('masks','region_masks'):
    for before in (root/'after'/subdir).glob('*.png'):
        with Image.open(before) as a,Image.open(root/'final'/subdir/before.name) as b:
            assert ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None,before
print(f'REALISM_EXPORTS_VERIFIED: {count} unchanged masks; four body dents in every view')
