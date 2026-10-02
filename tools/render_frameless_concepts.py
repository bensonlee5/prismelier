#!/usr/bin/env python3
"""Frameless low-light concept sheet; design previews only."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from render_preview import font
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/design/ambient/frameless'
OUT.mkdir(parents=True,exist_ok=True)
TIME=(160,151,133);COPPER=(132,100,76)

def label(im,name,value,x,y,color=TIME,scale=None,align='center'):
    if scale is None: scale = 52/65 if name == "Ambient" else 1
    page,glyphs=font(name)
    width=sum(glyphs[ord(c)]['xadvance'] for c in value)
    layer=Image.new('RGBA',(width+4,90),(0,0,0,0));cursor=2
    for c in value:
        g=glyphs[ord(c)];mask=page.crop((g['x'],g['y'],g['x']+g['width'],g['y']+g['height']))
        layer.paste(color+(255,),(cursor+g['xoffset'],g['yoffset']),mask);cursor+=g['xadvance']
    layer=layer.resize((round(layer.width*scale),round(layer.height*scale)),Image.Resampling.LANCZOS)
    im.paste(layer,(round(x-layer.width/2) if align=='center' else x,round(y)),layer)

faces=[]
for option in 'ABCD':
    im=Image.new('RGB',(416,416),'black')
    if option=='A':
        label(im,'Label','FRIDAY',208,133,COPPER)
        label(im,'Ambient','10:08',208,164)
        label(im,'Small','OCT 02',208,230,COPPER)
    elif option=='B':
        label(im,'Ambient','10:08',208,150,scale=1)
        label(im,'Label','FRIDAY / OCT 02',208,235,COPPER)
    elif option=='C':
        label(im,'Label','FRIDAY',102,133,COPPER,align='left')
        label(im,'Ambient','10:08',100,164,align='left')
        label(im,'Small','OCT 02',101,230,COPPER,align='left')
    else:
        label(im,'Label','FRIDAY',208,109,COPPER)
        label(im,'Ambient','10',208,135)
        label(im,'Ambient','08',208,191)
        label(im,'Small','OCT 02',208,264,COPPER)
    im.save(OUT/f'option-{option.lower()}.png');faces.append(im)

board=Image.new('RGB',(1000,1220),(19,22,26));d=ImageDraw.Draw(board)
f=lambda n:ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',n)
d.text((35,24),'QUIET FOUNDRY / FRAMELESS',font=f(27),fill=(225,220,211))
d.text((35,64),'Warm time • muted copper calendar • pure black background',font=f(18),fill=(155,160,167))
titles=['A / Calm center','B / Bigger time','C / Left aligned','D / Stacked digits']
notes=['Closest to the original, with all corners removed.','Larger clock; weekday and date on one line.','A quieter, editorial arrangement.','A compact two-line clock with calendar context.']
mask=Image.new('L',(416,416));ImageDraw.Draw(mask).ellipse((0,0,415,415),fill=255)
for i,im in enumerate(faces):
    x=35+(i%2)*500;y=143+(i//2)*530
    d.text((x,y-35),titles[i],font=f(23),fill=(225,220,211))
    d.ellipse((x-2,y-2,x+417,y+417),fill=(41,47,53))
    board.paste(im,(x,y),mask)
    d.text((x,y+435),notes[i],font=f(17),fill=(174,180,187))
d.text((35,1172),'Design previews only. Round outlines represent the watch edge; no border is drawn on the display.',font=f(15),fill=(139,147,155))
board.save(OUT/'comparison.png')
print(OUT/'comparison.png')
