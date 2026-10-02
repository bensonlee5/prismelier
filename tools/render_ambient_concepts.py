#!/usr/bin/env python3
"""Design mock-ups using shipped glyphs; not simulator or firmware evidence."""
from pathlib import Path
import json, math
from PIL import Image, ImageDraw, ImageFont
from render_preview import font
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/design/ambient'
OUT.mkdir(parents=True,exist_ok=True)
INK=(150,154,158)
SUB=(108,115,121)
COPPER=(132,100,76)

def text(image,name,value,center,top,color):
    page,glyphs=font(name)
    x=center-sum(glyphs[ord(c)]['xadvance'] for c in value)/2
    for c in value:
        g=glyphs[ord(c)]
        mask=page.crop((g['x'],g['y'],g['x']+g['width'],g['y']+g['height']))
        image.paste(color,(round(x+g['xoffset']),round(top+g['yoffset'])),mask)
        x+=g['xadvance']

faces=[]
for option in 'ABC':
    im=Image.new('RGB',(416,416),'black')
    if option=='A':
        text(im,'Ambient','10:08',208,150,INK)
        text(im,'Small','OCT 02',208,218,SUB)
    elif option=='B':
        text(im,'Label','FRIDAY',208,133,SUB)
        text(im,'Ambient','10:08',208,163,INK)
        text(im,'Small','OCT 02',208,229,SUB)
    else:
        text(im,'Ambient','10:08',208,150,(160,151,133))
        text(im,'Small','OCT 02',208,218,COPPER)
        d=ImageDraw.Draw(im)
        for x,dx in [(112,10),(304,-10)]:
            for y,dy in [(159,10),(244,-10)]:
                d.line([(x+dx,y),(x,y),(x,y+dy)],fill=COPPER,width=1)
    im.save(OUT/f'option-{option.lower()}.png')
    faces.append(im)

board=Image.new('RGB',(1428,660),(19,22,26));d=ImageDraw.Draw(board)
ui='/System/Library/Fonts/Helvetica.ttc'
f=lambda n:ImageFont.truetype(ui,n)
d.text((38,25),'PRISMELIER / LOW-LIGHT GLANCE',font=f(25),fill=(224,220,211))
d.text((38,62),'416 px design studies • black screen • no textures, seconds, or live gauges',font=f(17),fill=(148,155,163))
titles=['A  /  Essentials','B  /  Day at a glance','C  /  Quiet Foundry']
notes=['Time + month/day. My recommendation.','Adds the weekday for a little more context.','Minimal copper corners echo the full face.']
results={}
mask=Image.new('L',(416,416));ImageDraw.Draw(mask).ellipse((0,0,415,415),fill=255)
for i,im in enumerate(faces):
    x=38+i*470
    d.text((x,109),titles[i],font=f(22),fill=(230,225,215))
    d.ellipse((x-3,157,x+418,578),fill=(43,48,54))
    board.paste(im,(x,160),mask)
    d.text((x,596),notes[i],font=f(17),fill=(181,185,189))
    lit=sum(max(p)>0 for p in im.getdata());results['ABC'[i]]={'litPixels':lit,'fractionCircularScreen':round(lit/(math.pi*208**2),4)}
d.text((38,635),'Mock-ups only. Surrounding ring is presentation framing; actual brightness is controlled by the watch.',font=f(14),fill=(126,134,144))
board.save(OUT/'comparison.png')
(OUT/'pixel-estimates.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results))
