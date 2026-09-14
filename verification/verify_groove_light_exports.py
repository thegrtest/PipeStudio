from pathlib import Path
import json
from PIL import Image,ImageChops
root=Path(__file__).resolve().parents[1]
before=root/'examples/realism-refinement/final'
after=root/'examples/groove-light-study/final'
count=0
for subdir in ('masks','region_masks'):
    for source in (before/subdir).glob('*.png'):
        with Image.open(source) as a,Image.open(after/subdir/source.name) as b:
            assert ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None,source
        count+=1
infos=json.loads((after/'manifest.json').read_text())['samples']
assert len(infos)==3 and {i['camera_id'] for i in infos}=={'FRONT_45','REAR_45','OVERHEAD'}
for info in infos:
    assert info['appearance_version']==3
    assert len(info['lighting'])==9
    assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in info['recipe']['defects'])==4
    for light in info['lighting']:
        assert light['power_watts']>=0 and light['size']>0
report=json.loads((after/'verification.json').read_text())
report.update(unchanged_masks=count,three_views=True,fixture_metadata=True)
(after/'verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
