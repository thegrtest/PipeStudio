from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw
from inspect_body_illumination import ROOT,profile

base=ROOT/'verification'/'realism_v2'
original=json.loads((base/'final.json').read_text())
out=base/'fill_elevation'
canvas=Image.new('RGB',(1800,3*370),(20,25,28));draw=ImageDraw.Draw(canvas)
metrics={}
for row,(camera,data) in enumerate(original.items()):
    paths=[('Real',Path(data['reference']))]+[(f'Tilt {angle}',out/'all'/'images'/f'{camera.lower()}_tilt{angle}.png') for angle in (35,55,75)]
    target=np.array(profile(paths[0][1],camera))[1:9]
    metrics[camera]={}
    for col,(title,path) in enumerate(paths):
        if not path.exists():continue
        with Image.open(path) as im:
            im.thumbnail((450,310));canvas.paste(im,(col*450,row*370+28))
        observed=profile(path,camera)
        mae=round(float(np.abs(np.array(observed)[1:9]-target).mean()),2)
        metrics[camera][title]={'vertical_profile_error':mae,'profile':observed}
        draw.text((col*450+8,row*370+5),camera+' / '+title,fill='white')
        draw.text((col*450+8,row*370+326),f'Body vertical brightness MAE: {mae}',fill='white')
canvas.save(out/'compare.jpg',quality=95)
(out/'metrics.json').write_text(json.dumps(metrics,indent=2))
print(json.dumps({k:{t:v['vertical_profile_error'] for t,v in m.items()} for k,m in metrics.items()},indent=2))
