from pathlib import Path
from collections import Counter
import json
root=Path(__file__).resolve().parents[1]
inventory=json.loads((root/'verification/training-source-inventory.json').read_text())
report=[]
for source in inventory:
    if source['classes'].get('0')!='plastic_dent':continue
    folder=root/source['folder'];counts=Counter();groups=set();classes=Counter();first=None
    for path in sorted((folder/'metadata').glob('*.json')):
        data=json.loads(path.read_text());counts['frames']+=1
        positive=[a for a in data['annotations'] if a['bbox_xywh']]
        counts['positive_frames']+=bool(positive)
        classes.update(a['class_name'] for a in positive)
        groups.add(data.get('split_group') or data.get('specimen_group'))
        for crop in data.get('crops',[]):
            category='whole_shell' if crop['region']=='flashlight' else 'region'
            counts[category+'_crops']+=1
            counts[category+'_positive_crops']+=bool(crop['annotations'])
            x,y,w,h=crop['source_bbox_xywh']
            counts[category+'_edge_crops']+=bool(x<=0 or y<=0 or x+w>=data['width'] or y+h>=data['height'])
            first=first or crop
    out=dict(source=source['folder'],counts=dict(counts),groups=len(groups),classes=dict(classes),example_crop=first)
    report.append(out);print(json.dumps({k:v for k,v in out.items() if k!='example_crop'}),flush=True)
(root/'verification/training-crop-inventory.json').write_text(json.dumps(report,indent=2))
