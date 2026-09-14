from pathlib import Path
from PIL import Image, ImageDraw
root = Path(__file__).resolve().parents[1]
folder = root/'examples/rolling-shells/dirty-defect-loop'
sheet = Image.new('RGB', (1600, 840), (15, 17, 18))
draw = ImageDraw.Draw(sheet)
for index, frame in enumerate((1, 9, 17, 25)):
    with Image.open(folder/'frames'/f'shell_{frame:04d}.png') as image:
        thumb = image.convert('RGB').resize((800, 400), Image.Resampling.LANCZOS)
    x, y = (index % 2)*800, (index // 2)*420
    sheet.paste(thumb, (x, y+20)); draw.text((x+8, y+4), f'Frame {frame}', fill='white')
sheet.save(folder/'motion-check.jpg', quality=94, subsampling=0)
print(folder/'motion-check.jpg')
