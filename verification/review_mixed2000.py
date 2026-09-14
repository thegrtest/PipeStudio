"""Labeled review thumbnails from completed files only; originals are untouched."""
from pathlib import Path
import json
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(r'C:\Users\daugh\OneDrive\Desktop\BrassSynthetic2000')
out=Path(__file__).resolve().parent/'mixed2000_review.jpg'
selected=[]
for batch in range(1,5):
    folder=ROOT/f'batch_{batch:02d}'/'all'
    samples=json.loads((folder/'manifest.json').read_text())['samples']
    # One clean sample and one small example per class where available.
    chosen=[]
    for kind in ('NONE','FOLD','DENT'):
        candidates=[s for s in samples if s['defect_type']==kind and (kind=='NONE' or s['severity']=='small')]
        if not candidates: candidates=[s for s in samples if s['defect_type']==kind]
        if candidates: chosen.append(candidates[0])
    selected.extend((folder,s) for s in chosen)
canvas=Image.new('RGB',(1200,325*4),'#111c23');draw=ImageDraw.Draw(canvas)
font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',13)
for index,(folder,item) in enumerate(selected):
    with Image.open(folder/item['image']) as source:
        image=source.convert('RGB');image.thumbnail((390,275))
    x=(index%3)*400+(400-image.width)//2;y=(index//3)*325
    box=item['bbox_xywh']
    if box:
        sx=image.width/item['width'];sy=image.height/item['height']
        bx,by,bw,bh=box
        ImageDraw.Draw(image).rectangle((bx*sx,by*sy,(bx+bw)*sx,(by+bh)*sy),outline='#ff9438' if item['class_id']==0 else '#39e9ff',width=2)
    canvas.paste(image,(x,y))
    draw.text(((index%3)*400+8,y+280),f'{folder.parent.name} / {item["defect_type"]} / {item["severity"]}',font=font,fill='#eed197')
    draw.text(((index%3)*400+8,y+300),item['parameters']['environment']+' / '+item['sample_id'],font=font,fill='white')
canvas.save(out,quality=95)
print(out)
