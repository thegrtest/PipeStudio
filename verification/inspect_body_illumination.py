"""Compare vertical brightness through the pipe, excluding shoulder and mount."""
import json,sys
from pathlib import Path
from PIL import Image
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
boxes={'CAM2534':(.47,.211,.80,.398),'CAM5080':(.16,.435,.65,.674),'CAM7650':(.26,.710,.73,.958)}
def profile(path,camera):
    with Image.open(path) as im:
        box=tuple(round(v*im.size[i%2]) for i,v in enumerate(boxes[camera]))
        p=np.asarray(im.crop(box)).mean(1)@np.array([.2126,.7152,.0722])
        return [round(float(q.mean()),1) for q in np.array_split(p,10)]
if __name__=='__main__':
    report=json.loads((ROOT/'verification'/'realism_v2'/((sys.argv[1] if len(sys.argv)>1 else 'final')+'.json')).read_text())
    print(json.dumps({c:{k:profile(ROOT/r[k],c) for k in ('reference','render')} for c,r in report.items()},indent=2))
