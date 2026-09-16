"""Reference crops paired with saved eval overlays; no prediction inference."""
from pathlib import Path
import random
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
real=ROOT.parent/'BrassModel11'/'all'
evals=ROOT.parent/'eval_20260914_122143'/'annotated'/'latest_ckpt'
out=ROOT/'verification'/'realism_v2';out.mkdir(parents=True,exist_ok=True)
rows=[]
for session in ('2026-08-19GodsLight','2026-08-20'):
    for label in sorted((real/session/'labels').glob('*.txt')):
        image=real/session/'images'/(label.stem+'.jpg')
        if not image.exists():continue
        for line in label.read_text().splitlines():
            values=line.split()
            if len(values)==5 and values[0]=='0':rows.append((session,image,tuple(map(float,values[1:]))))
random.Random(914).shuffle(rows)
rows=rows[:36]
canvas=Image.new('RGB',(1440,6*208),(22,25,28));draw=ImageDraw.Draw(canvas)
for i,(session,path,box) in enumerate(rows):
    x=i%6*240;y=i//6*208
    with Image.open(path) as im:
        cx,cy,w,h=box;W,H=im.size
        rect=(max(0,round((cx-w*.85)*W)),max(0,round((cy-h*1.15)*H)),
              min(W,round((cx+w*.85)*W)),min(H,round((cy+h*1.15)*H)))
        detail=im.crop(rect);detail.thumbnail((236,88));canvas.paste(detail,(x,y+17))
    prediction=evals/('all_'+session+'__'+path.name)
    if prediction.exists():
        with Image.open(prediction) as im:
            detail=im.crop(rect);detail.thumbnail((236,88));canvas.paste(detail,(x,y+115))
    draw.text((x+3,y+2),path.stem[-20:],fill='white')
    draw.text((x+3,y+102),'Saved eval overlay',fill='#b9d1e0')
canvas.save(out/'fold_eval_crops.jpg',quality=95)
print('36 real Fold crops paired with saved latest-checkpoint overlays:',out/'fold_eval_crops.jpg')
