"""Check the first complete production camera set without changing its exports."""
import json
import sys
from pathlib import Path
from PIL import Image, ImageChops

folder=Path(sys.argv[1])
infos=[json.loads((folder/'metadata'/f'flashlight_00000_{camera}.json').read_text())
       for camera in ('front_45','rear_45','overhead')]
report=dict(passed=False,images=3,shell_instances=0,visible_regions=0,visible_defects=0,crops=0,
            four_body_dents_per_row=True,camera_ids=[info['camera_id'] for info in infos])

def check_annotations(info,key,label_dir):
    annotations=info[key]
    width,height=info['width'],info['height']
    expected=[]
    masks={}
    for annotation in annotations:
        with Image.open(folder/annotation['mask']) as source:
            mask=source.convert('L')
        assert mask.size==(width,height)
        histogram=mask.histogram()
        assert not sum(histogram[1:255])
        assert histogram[255]==annotation['visible_pixels']
        bounds=mask.getbbox()
        box=[bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]] if bounds else None
        assert box==annotation['bbox_xywh']
        if box:
            x,y,w,h=box
            expected.append([annotation['class_id'],(x+w/2)/width,(y+h/2)/height,w/width,h/height])
        masks[annotation['mask']]=mask
    path=folder/label_dir/(Path(info['image']).stem+'.txt')
    actual=[[float(value) for value in line.split()] for line in path.read_text().splitlines()]
    assert len(actual)==len(expected),path
    assert all(len(row)==5 for row in actual)
    assert all(abs(a-b)<1e-7 for row,want in zip(actual,expected) for a,b in zip(row,want))
    return masks,len(expected)

for info in infos:
    assert info['appearance_version']==8
    assert len(info['recipe']['items'])==6
    assert info['recipe']['required_body_dents']==4
    assert sum(d['kind']=='plastic_dent' and d['region']=='BODY' for d in info['recipe']['defects'])==4
    assert info['recipe']['items']==infos[0]['recipe']['items']
    assert len(info['region_annotations'])==24
    assert len(info['shell_annotations'])==6
    regions,visible=check_annotations(info,'region_annotations','regions/labels')
    report['visible_regions']+=visible
    shells,visible=check_annotations(info,'shell_annotations','shells/labels')
    assert visible==6
    report['shell_instances']+=visible
    defects,visible=check_annotations(info,'annotations','labels')
    report['visible_defects']+=visible
    for shell in info['shell_annotations']:
        union=Image.new('L',(info['width'],info['height']))
        for region in info['region_annotations']:
            if region['flashlight_id']==shell['flashlight_id']:
                union=ImageChops.lighter(union,regions[region['mask']])
        assert ImageChops.difference(union,shells[shell['mask']]).getbbox() is None
    with Image.open(folder/info['image']) as source:
        source=source.convert('RGB')
        shell_crops=[crop for crop in info['crops'] if crop['region']=='flashlight']
        assert len(shell_crops)==6
        for crop in info['crops']:
            x,y,w,h=crop['source_bbox_xywh']
            with Image.open(folder/crop['image']) as extracted:
                assert extracted.size==(w,h)
                assert ImageChops.difference(extracted.convert('RGB'),source.crop((x,y,x+w,y+h))).getbbox() is None
            for defect in crop['annotations']:
                ax,ay,aw,ah=defect['bbox_xywh']
                assert 0<=ax<ax+aw<=w and 0<=ay<ay+ah<=h
            report['crops']+=1
report['passed']=True
(folder/'startup-label-validation.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
