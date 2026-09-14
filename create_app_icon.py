"""Generate a simple geometric application icon."""
from pathlib import Path
from PIL import Image, ImageDraw

folder=Path(__file__).resolve().parent/'assets'
folder.mkdir(exist_ok=True)
image=Image.new('RGBA',(256,256),(17,23,30,255))
draw=ImageDraw.Draw(image)
draw.rounded_rectangle((8,8,248,248),radius=50,fill='#1b242e',outline='#354452',width=3)
draw.polygon([(48,71),(211,101),(211,159),(48,194)],fill='#a47236')
draw.polygon([(48,71),(211,101),(204,119),(48,111)],fill='#edc780')
draw.line([(77,138),(135,137),(148,155),(163,137),(206,134)],fill='#624320',width=5)
draw.ellipse((23,69,92,196),fill='#edb86a',outline='#f6dca9',width=3)
draw.ellipse((37,88,78,177),fill='#11171e',outline='#80582e',width=5)
draw.ellipse((194,101,227,160),fill='#c59049',outline='#edc780',width=3)
draw.ellipse((202,112,218,149),fill='#11171e')
image.save(folder/'pipe.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
