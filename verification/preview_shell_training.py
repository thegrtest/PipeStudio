from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
root=Path(__file__).resolve().parents[1]
folder=root/'datasets/Shell_Defects_Training_20260913'
base=folder/'crops/regions'
best={}
for line in (base/'index.jsonl').read_text().splitlines():
    row=json.loads(line)
    if row['heavy_dirt']:continue
    for a in row['annotations']:
        area=a['visible_pixels']
        if min(a['bbox_xywh'][2:])<8:continue
        score=(row.get('appearance_version') or 0, min(area,10000), min(row['width'],row['height']))
        if a['class_id'] not in best or score>best[a['class_id']][0]:best[a['class_id']]=(score,row,a)
sheet=Image.new('RGB',(1600,850),(19,22,24));draw=ImageDraw.Draw(sheet)
font_path=Path('C:/Windows/Fonts/segoeui.ttf')
font=ImageFont.truetype(str(font_path),22) if font_path.exists() else ImageFont.load_default()
small=ImageFont.truetype(str(font_path),15) if font_path.exists() else ImageFont.load_default()
for class_id in range(7):
    _,row,a=best[class_id]
    with Image.open(base/row['image']) as im:image=im.convert('RGB')
    overlay=ImageDraw.Draw(image)
    for annotation in row['annotations']:
        x,y,w,h=annotation['bbox_xywh']
        overlay.rectangle((x,y,x+w-1,y+h-1),outline='#70ff88',width=max(1,round(max(image.size)/260)))
    image.thumbnail((380,340),Image.Resampling.LANCZOS)
    x=(class_id%4)*400;y=(class_id//4)*425
    sheet.paste(image,(x+(400-image.width)//2,y+40+(340-image.height)//2))
    draw.text((x+15,y+8),f"{class_id}  {a['class_name']}",font=font,fill='white')
    draw.text((x+15,y+389),f"{row['split']} | {row['camera_id']}",font=small,fill='#bdc7ca')
draw.text((1220,490),'Verified defect labels',font=font,fill='white')
draw.text((1220,530),'7 classes | YOLO + COCO',font=small,fill='#bdc7ca')
draw.text((1220,562),'All crops share their parent split',font=small,fill='#bdc7ca')
sheet.save(folder/'preview.jpg',quality=94,subsampling=0)
print(folder/'preview.jpg')
