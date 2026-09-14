"""Rasterize reference-style lettering for a shallow geometric face stamp."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import math
root=Path(__file__).resolve().parents[1]
size=1024
canvas=Image.new('L',(size,size))
font=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',146)
def glyph(char,angle,radius):
    im=Image.new('L',(240,240));draw=ImageDraw.Draw(im)
    draw.text((120,120),char,font=font,anchor='mm',fill=255,stroke_width=1)
    im=im.rotate(angle-90,resample=Image.Resampling.BICUBIC)
    a=math.radians(angle)
    x=round(size/2+radius*math.cos(a)-120);y=round(size/2-radius*math.sin(a)-120)
    canvas.paste(im,(x,y),im)
for char,angle in zip('FEDERAL',(164,139,114,89,64,39,14)):glyph(char,angle,342)
for char,angle in [('1',223),('2',242),('1',298),('2',317)]:glyph(char,angle,325)
folder=root/'flashlight_lab'/'assets';folder.mkdir(exist_ok=True)
canvas.filter(ImageFilter.GaussianBlur(1.25)).save(folder/'cap_stamp_v2.png')
print(folder/'cap_stamp_v2.png')
