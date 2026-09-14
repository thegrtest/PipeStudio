"""Create readable, correctly proportioned exterior printing for the cylinder."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import random
root=Path(__file__).resolve().parents[1]
folder=root/'flashlight_lab'/'assets'
# Circumference / printed body length gives nearly square physical texels.
# A 1024 x 2048 map stretched letter heights around the body by ~2.5x.
width,height=2611,2048
brand=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',190)
small=ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf',132)
for index in range(2):
    strip=Image.new('L',(1550,470))
    draw=ImageDraw.Draw(strip)
    draw.text((810,148),'FEDERAL',font=brand,anchor='mm',fill=255)
    draw.text((810,357),'2¾" 70mm',font=small,anchor='mm',fill=255)
    # Arc mark after FEDERAL, as in the reference. F starts at the brass end.
    for radius in (49,64,79):
        draw.arc((1378-radius,148-radius,1378+radius,148+radius),210,510,fill=255,width=9)
    strip=strip.rotate(90,expand=True)
    canvas=Image.new('L',(width,height))
    canvas.paste(strip,(round(.75*width)-148,height//2-strip.height//2))
    draw=ImageDraw.Draw(canvas);rng=random.Random(814+index)
    for _ in range(500):
        x=rng.randrange(round(.75*width)-110,round(.75*width)+310);y=rng.randrange(300,1740)
        draw.ellipse((x,y,x+rng.randrange(1,3),y+rng.randrange(1,4)),fill=0)
    canvas.save(folder/f'body_print_v2_{index}.png')
print('Body ink assets created')
