"""Verify completed assembly RGB, masks, YOLO labels and specimen splits."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

import numpy as np
from PIL import Image,ImageFilter

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from assembly_plan import visible_box,yolo_line
from assembly_generate import complete
from domain_render import atomic_json


def verify(root):
    root=Path(root)
    plan=json.loads((root/'plan.json').read_text())
    result=dict(frames=0,parts=0,defects=Counter(),image_sizes=Counter())
    for row in plan['rows']:
        assert complete(root,row),row['sample_id']
        info=json.loads((root/'metadata'/(row['sample_id']+'.json')).read_text())
        w,h=Image.open(root/info['image']).size
        assert (w,h)==(info['width'],info['height'])
        result['image_sizes'][str((w,h))]+=1
        for key,sub in (('annotations','all/labels'),('parts','tracking/all/labels')):
            actual=(root/sub/(info['sample_id']+'.txt')).read_text().splitlines()
            expected=[]
            for a in info[key]:
                mask=np.asarray(Image.open(root/a['mask']).convert('L'))>127
                assert visible_box(mask,minimum=1)==a['bbox_xywh'],a
                assert int(mask.sum())==a['visible_pixels']
                expected.append(yolo_line(a['class_id'],a['bbox_xywh'],w,h))
                if key=='annotations':
                    shell=next(p for p in info['parts'] if p['name']=='shell' and p['specimen_id']==a['specimen_id'])
                    outer=np.asarray(Image.open(root/shell['mask']).convert('L').filter(ImageFilter.MaxFilter(3)))>127
                    assert not (mask & ~outer).any(),a
                    result['defects'][a['name']]+=1
                else:result['parts']+=1
            assert actual==expected,(info['sample_id'],sub)
        if info['recipe']['condition']=='good':assert not info['annotations']
        result['frames']+=1
    splits=[]
    for split in ('train','val'):
        filenames=[Path(p).stem for p in (root/(split+'.txt')).read_text().splitlines()]
        groups={json.loads((root/'metadata'/(n+'.json')).read_text())['split_group'] for n in filenames}
        splits.append(groups)
    assert not splits[0]&splits[1]
    result['split_groups']=[len(s) for s in splits];result['passed']=True
    atomic_json(root/'validation.json',result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path)
    print(json.dumps(verify(p.parse_args().root),indent=2))
