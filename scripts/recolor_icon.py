from PIL import Image
import colorsys
from pathlib import Path
import pefile
repo=Path(__file__).resolve().parents[1]
pe=pefile.PE(str(repo/'dist/Compara OFX.exe'))
resource=next(e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id==3).directory.entries[0].directory.entries[0].data.struct
import io
im=Image.open(io.BytesIO(pe.get_data(resource.OffsetToData,resource.Size))).convert('RGBA')
import os
os.chdir(repo)
out=im.copy(); pix=out.load()
for y in range(out.height):
 for x in range(out.width):
  r,g,b,a=pix[x,y]
  h,s,v=colorsys.rgb_to_hsv(r/255,g/255,b/255)
  if a and s>.25 and .27<h<.49:
   nr,ng,nb=colorsys.hsv_to_rgb(221/360, min(1,s*.82),v)
   pix[x,y]=(round(nr*255),round(ng*255),round(nb*255),a)
out.save('assets/comparaofx-2.0-azul.png')
out.save('assets/comparaofx-2.0-azul.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
canvas=Image.new('RGBA',(532,256),'white');canvas.alpha_composite(im,(0,0));canvas.alpha_composite(out,(276,0));canvas.convert('RGB').save('assets/comparacao-icones.png')
