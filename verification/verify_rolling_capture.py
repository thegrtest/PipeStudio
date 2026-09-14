"""Independent pixel and identity checks for rolling captures, plus an overlay."""
from pathlib import Path
import json
import sys
from collections import defaultdict
from PIL import Image, ImageChops, ImageDraw

folder=Path(sys.argv[1])
manifest=json.loads((folder/'manifest.json').read_text())
infos=[json.loads((folder/info['metadata']).read_text()) if 'recipe' not in info else info for info in manifest['images']]
assert infos
visibility=defaultdict(list)
totals=dict(images=len(infos),visible_shells=0,visible_regions=0,visible_defects=0,full_shell_crops=0,crops=0)

def labels(path,annotations,width,height):
    wanted=[]
    for annotation in annotations:
        if not annotation['bbox_xywh']:continue
        x,y,w,h=annotation['bbox_xywh']
        wanted.append([annotation['class_id'],(x+w/2)/width,(y+h/2)/height,w/width,h/height])
    actual=[[float(value) for value in line.split()] for line in path.read_text().splitlines()]
    assert len(actual)==len(wanted),path
    assert all(len(row)==5 for row in actual)
    assert all(abs(a-b)<1e-7 for row,expected in zip(actual,wanted) for a,b in zip(row,expected)),path

for info in infos:
    assert info['motion_blur'] is False
    assert info['split_group'] in manifest.get('split_groups',[manifest['split_group']])
    size=(info['width'],info['height'])
    by_shell=defaultdict(list)
    shell_masks={}
    for key,directory,metric in [('region_annotations','regions/labels','visible_regions'),
                                  ('shell_annotations','shells/labels','visible_shells'),
                                  ('annotations','labels','visible_defects')]:
        labels(folder/directory/(Path(info['image']).stem+'.txt'),info[key],*size)
        for annotation in info[key]:
            with Image.open(folder/annotation['mask']) as original:mask=original.convert('L')
            assert mask.size==size
            histogram=mask.histogram()
            assert not sum(histogram[1:255])
            assert histogram[255]==annotation['visible_pixels']
            bounds=mask.getbbox()
            box=[bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]] if bounds else None
            assert box==annotation['bbox_xywh']
            assert annotation['track_id']==f'{info["sequence_id"]}:{annotation["flashlight_id"]}'
            if box:totals[metric]+=1
            if key=='region_annotations':by_shell[annotation['flashlight_id']].append(mask)
            if key=='shell_annotations':shell_masks[annotation['flashlight_id']]=mask
    shell_union=Image.new('L',size)
    for shell_id,mask in shell_masks.items():
        assert ImageChops.multiply(shell_union,mask).getbbox() is None,'Two physical shells share mask pixels'
        shell_union=ImageChops.lighter(shell_union,mask)
        regions=Image.new('L',size)
        for region in by_shell[shell_id]:regions=ImageChops.lighter(regions,region)
        assert ImageChops.difference(regions,mask).getbbox() is None
    defect_visibility={a['defect_id']:a['visible_pixels'] for a in info['annotations']}
    for defect in info['recipe']['defects']:
        if defect['flashlight_id'] in shell_masks and shell_masks[defect['flashlight_id']].getbbox():
            track_id=f'{info["sequence_id"]}:{defect["flashlight_id"]}'
            visibility[(info['camera_id'],track_id)].append(defect_visibility.get(defect['id'],0)>0)
    # The front camera orders distinct physical instances from left to right.
    if info['camera_id']=='FRONT_45':
        visible=[a for a in info['shell_annotations'] if a['bbox_xywh']]
        assert len(visible)>=7
        assert [a['flashlight_id'] for a in visible]==sorted(a['flashlight_id'] for a in visible)
        centers=[a['bbox_xywh'][0]+a['bbox_xywh'][2]/2 for a in visible]
        assert centers==sorted(centers)
        if manifest.get('randomized_defects'):
            assert len({a['source_variant_id'] for a in visible})==len(visible),'Incoming randomized shells must be unique'
        else:
            assert len({a['source_variant_id'] for a in visible})<len(visible),'Test must include duplicated source variants'
    with Image.open(folder/info['image']) as original:source=original.convert('RGB')
    for crop in info['crops']:
        x,y,w,h=crop['source_bbox_xywh']
        with Image.open(folder/crop['image']) as image:
            assert image.size==(w,h)
            assert ImageChops.difference(image.convert('RGB'),source.crop((x,y,x+w,y+h))).getbbox() is None
        labels((folder/crop['image']).with_suffix('.txt'),crop['annotations'],w,h)
        if crop['region']=='flashlight':
            assert x>0 and y>0 and x+w<size[0] and y+h<size[1]
            totals['full_shell_crops']+=1
        totals['crops']+=1
transitions=sum(any(values) and not all(values) for values in visibility.values())
assert transitions>0,'Need a visible shell whose defect rotates out of sight'
report=dict(passed=True,**totals,tracks_with_defects_rotating_in_and_out=transitions,
            cameras=sorted({info['camera_id'] for info in infos}),stable_track_ids=True,
            masks_disjoint=True,crops_pixel_exact=True,source_variants=manifest['source_variant_count'])
if manifest.get('randomized_defects'):
    by_pass=defaultdict(list)
    for info in infos:by_pass[info['pass_index']].append(info)
    assert len(by_pass)>=2
    fingerprints=set();all_track_ids=set()
    for pass_index,views in by_pass.items():
        recipe=views[0]['recipe'];items=recipe['items']
        assert all(info['recipe']['items']==items for info in views),'Defects changed within a pass'
        fingerprints.add(recipe['recipe_sha256'])
        ids={annotation['track_id'] for annotation in views[0]['shell_annotations']}
        assert not ids&all_track_ids,'Different passes share physical track IDs'
        all_track_ids|=ids
        for offset in range(0,len(items)-5,6):
            assert sum(bool(item['defect'] and item['defect']['kind']=='plastic_dent' and item['defect']['region']=='BODY')
                for item in items[offset:offset+6])==recipe['randomization_settings']['body_dents']
        for defect in recipe['defects']:
            if defect['kind']=='body_twist':assert abs(defect['twist_degrees'])<=recipe['randomization_settings']['twist_limit']
    assert len(fingerprints)==len(by_pass)
    report.update(randomized_passes=len(by_pass),distinct_recipes=True,four_body_dents_per_six=True)
(folder/'validation.json').write_text(json.dumps(report,indent=2))
front=[info for info in infos if info['camera_id']=='FRONT_45']
selected=front[::max(1,len(front)//3)][:3]
sheet=Image.new('RGB',(900,200*len(selected)),(18,22,26))
for index,info in enumerate(selected):
    with Image.open(folder/info['image']) as original:image=original.convert('RGB')
    draw=ImageDraw.Draw(image)
    for annotation in info['annotations']:
        if annotation['bbox_xywh']:
            x,y,w,h=annotation['bbox_xywh']
            draw.rectangle((x,y,x+w-1,y+h-1),outline='#70ff88',width=3)
    image=image.resize((400,200))
    sheet.paste(image,(0,index*200))
    draw=ImageDraw.Draw(sheet)
    visible=sum(bool(a['bbox_xywh']) for a in info['annotations'])
    draw.text((420,index*200+55),f'Frame {info["frame"]} - {info["timestamp_seconds"]:.2f}s\n{visible} visible defects\nGreen: defect support boxes',fill='white',spacing=8)
sheet.save(folder/'rolling-label-preview.png')
print(json.dumps(report,indent=2))
