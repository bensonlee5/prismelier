#!/usr/bin/env python3
"""Design-only render of the 416px layout; fictional values, not a simulator.
Uses the very same BMFont atlases shipped with the watch application.
"""
from pathlib import Path
from PIL import Image, ImageDraw
import math, re, json
ROOT = Path(__file__).resolve().parents[1]
S = 3
THEMES = json.loads((ROOT/'resources/themes.json').read_text())
COL = dict(ink='#f2edd8',copper='#d98b52',green='#c7ff70',pink='#f474e8',cyan='#6be4de',muted='#786d82',panel='#122325')
class Canvas:
    def __init__(self, theme=0, photo=False):
        self.theme=THEMES[theme]['colors']
        self.base=Image.open(ROOT/'resources/textures/foundry-background-indexed.png').convert('RGB') if photo else None
        self.im=Image.new('RGBA',(416*S,416*S),(0,0,0,0)) if photo else Image.new('RGB',(416*S,416*S),'black'); self.d=ImageDraw.Draw(self.im); self.fonts={}; self.boxes=[]
    def color(self,c):
        value=COL.get(c,c)
        if isinstance(value,str) and value.startswith('#'):
            return '#'+self.theme.get(value[1:].upper(),value[1:])
        return value
    def line(self,a,b,c,w=1): self.d.line(tuple(round(v*S) for v in (*a,*b)),fill=self.color(c),width=max(1,round(w*S)))
    def circle(self,x,y,r,c,fill=False,w=1):
        box=tuple(round(v*S) for v in (x-r,y-r,x+r,y+r)); self.d.ellipse(box,fill=self.color(c) if fill else None,outline=None if fill else self.color(c),width=w*S)
    def rect(self,x,y,w,h,c,fill=True,r=0):
        self.d.rounded_rectangle(tuple(round(v*S) for v in (x,y,x+w,y+h)),radius=r*S,fill=self.color(c) if fill else None,outline=None if fill else self.color(c),width=S)
    def polygon(self,points,c): self.d.polygon([(round(x*S),round(y*S)) for x,y in points],fill=self.color(c))
    def text(self,x,y,font,text,c):
        if font not in self.fonts:
            f={}
            for ln in (ROOT/f'resources/fonts/{font}.fnt').read_text().splitlines():
                if ln.startswith('char '):
                    fields=dict((k,int(v)) for k,v in re.findall(r'(\w+)=(-?\d+)',ln)); f[fields['id']]=fields
            self.fonts[font]=(f,Image.open(ROOT/f'resources/fonts/{font}.png').convert('L'))
        f,atlas=self.fonts[font]; width=sum(f[ord(t)]['xadvance'] for t in text); px=x-width/2
        self.boxes.append((font,text,px,y,width))
        for t in text:
            g=f[ord(t)]; mask=atlas.crop((g['x'],g['y'],g['x']+g['width'],g['y']+g['height'])).resize((g['width']*S,g['height']*S))
            patch=Image.new('RGB',mask.size,self.color(c)); self.im.paste(patch,(round((px+g['xoffset'])*S),round((y+g['yoffset'])*S)),mask); px+=g['xadvance']
    def radial(self,cx,cy,inner,outer,a,c,w=1): self.line(point(cx,cy,inner,a),point(cx,cy,outer,a),c,w)
    def finish(self):
        layer=self.im.resize((416,416),Image.Resampling.LANCZOS)
        return Image.alpha_composite(self.base.convert('RGBA'),layer).convert('RGB') if self.base is not None else layer
def point(x,y,r,a): return x+math.cos(math.radians(a))*r,y+math.sin(math.radians(a))*r

def screw(c,x,y,color='copper'):
    c.circle(x,y,3,color,True);c.line((x-2,y+1),(x+2,y-1),'#241620')
def gear(c,x,y,r,color):
    for i in range(12): c.radial(x,y,r-2,r+3,i*30,color,4)
    c.circle(x,y,r-3,color,w=3); c.circle(x,y,r-8,color)
    for a in range(3):c.radial(x,y,4,r-8,a*120+25,color,3)
    c.circle(x,y,4,'#d6d9bf',True);screw(c,x,y)
def weather(c,x,y,kind='partly',stale=False,night=False):
    color='copper' if stale else 'cyan'
    def path(points,col=color):trace(c,[(x+a,y+b) for a,b in points],col,2)
    if kind=='sun':
        if night:path([(-4,-11),(-10,-7),(-12,0),(-9,8),(-2,11),(6,8),(10,3),(3,4),(-3,0),(-5,-6),(-4,-11)])
        else:
            c.circle(x,y,7,color,w=2)
            for a in range(8):c.radial(x,y,11,14,a*45,color,2)
    elif kind=='wind':
        path([(-14,-5),(7,-5),(10,-8),(8,-11),(5,-11)]);path([(-10,1),(14,1),(16,4),(13,7)]);c.line((x-14,y+7),(x+5,y+7),color,2)
    elif kind=='fog':
        for xx,yy in [(14,-5),(10,1),(14,7)]:c.line((x-xx,y+yy),(x+xx,y+yy),color,2)
    else:
        if kind=='partly':
            path([(3,-13),(7,-16),(12,-15),(15,-11),(14,-6)],'copper')
            for a in (270,315,0):c.radial(x+8,y-10,8,10,a,'copper',2)
        path([(-12,7),(-15,4),(-15,0),(-12,-4),(-7,-5),(-5,-10),(0,-13),(6,-11),(9,-6),(10,-2),(14,0),(16,4),(13,7),(-12,7)])
        if kind=='rain':
            for a in (-7,2,11):c.line((x+a,y+11),(x+a-3,y+16),color,2)
        elif kind=='storm':path([(3,9),(-2,15),(5,15),(0,16)])
        elif kind=='snow':
            c.line((x,y+10),(x,y+16),color,2);c.line((x-4,y+12),(x+4,y+17),color,2);c.line((x-4,y+17),(x+4,y+12),color,2)
    if kind=='unknown' or stale:c.line((x-17,y+16),(x+17,y-17),'copper',2)
def solar(c,up=False,missing=False,stale=False,clock=None,photo=False):
    x,y=247,295;color='#777f70' if missing else '#27645d' if up else '#a04d30';suny=y-4 if up else y
    for a in range(180,360,15):c.line(point(x,suny,8,a),point(x,suny,8,a+15),color,2)
    c.line((x-14,y),(x+12,y),color,2)
    for a in (220,270,320):c.radial(x,suny,11,14,a,color,2)
    if not missing:
        tipy=y-12 if up else y+10;basey=tipy+5 if up else tipy-5
        c.line((x+16,y-12 if up else y+1),(x+16,y-3 if up else y+10),color,2);c.line((x+12,basey),(x+16,tipy),color,2);c.line((x+20,basey),(x+16,tipy),color,2)
    c.text(307,278,'Small',clock or ('--:--' if missing else '06:48' if up else '18:42'),'#183b3b')
    if stale:c.circle(340,307,3,'copper')
def trace(c,points,color,w=1):
    for a,b in zip(points,points[1:]):c.line(a,b,color,w)
def junction(c,x,y,color):c.circle(x,y,3,color);c.circle(x,y,1,color,True)
def architecture(c):
    c.circle(208,208,199,'#071214',True);c.circle(208,208,198,'#344741')
    c.rect(102,50,106,30,'#102226',True,7);c.rect(219,50,91,30,'#102226',True,7)
    c.rect(62,84,292,94,'#452744',True,14)
    for grain in range(5):c.line((70,88+grain*19),(346,90+grain*19),'#85506d')
    c.rect(69,90,278,81,'#080f13',True,9);c.rect(62,84,292,94,'copper',False,14);c.line((80,85),(336,85),'#f2bf8c')
    c.rect(160,177,96,28,'#102226',True,5);c.rect(160,177,96,28,'#3c6260',False,5)
    c.rect(218,209,137,115,'panel',True,13);c.rect(218,209,137,115,'copper',False,13)
    c.polygon([(229,273),(343,273),(349,280),(344,310),(227,310),(223,303)],'#d6d9bf');c.line((231,275),(339,275),'#f5f5db')
    c.rect(83,342,254,38,'#080f13',True,7);c.rect(83,342,254,38,'#6b4839',False,7)

def robotics(c):
    for x in (31,373):
        c.rect(x,162,12,44,'#080f13',True,3)
        for pin in range(7):c.line((x+3,166+pin*5),(x+9,166+pin*5),'copper',2)
    for ribbon in range(4):
        trace(c,[(82+ribbon*5,73),(69+ribbon*5,75),(49+ribbon*5,94),(49+ribbon*5,124)],'#8b6544')
        trace(c,[(334-ribbon*5,73),(347-ribbon*5,75),(367-ribbon*5,94),(367-ribbon*5,124)],'#335657')
    trace(c,[(27,222),(31,291),(66,330),(78,330)],'#4f958b',2)
    trace(c,[(386,225),(382,300),(347,333),(328,333)],'#8b6544',2)
    gear(c,365,239,11,'cyan');screw(c,219,333);screw(c,351,322)
    c.rect(181,383,54,15,'#080f13',True,3);c.rect(181,383,54,15,'#3c6260',False,3)
    for pin in range(6):c.line((185+pin*9,380),(185+pin*9,383),'copper',2)

def machine(c):
    c.circle(137,267,74,'#452744',True);c.circle(137,267,71,'#85506d');c.circle(137,267,67,'copper',w=2);c.circle(137,267,64,'#091b23',True)
    for x,y in [(87,213),(188,213),(87,322),(188,322)]:screw(c,x,y)

def calendar(c,weekday=4,date='Oct 1',blank=False):
    for index,initial in enumerate('SMTWTFS'):
        x,y=point(208,208,188,210+index*20);selected=index==weekday and not blank
        c.circle(x,y,12,'#27645d' if selected else '#071214',True)
        if selected:c.circle(x,y,12,'copper')
        if not blank:c.text(x,y-12,'Small',initial,'#f2bf8c' if selected else '#74aca0')
    if not blank:c.text(208,175,'Small',date,'ink')

def temperature_gauge(c,temperature=72,fahrenheit=True,missing=False,stale=False):
    low,high=(0,120) if fahrenheit else(-20,40);f=0 if missing else max(0,min(1,(temperature-low)/(high-low)))
    for j in range(72):
        a,b=135+270*j/72,135+270*(j+1)/72;active=not missing and (j+.5)/72<=f
        color=('#80665c' if stale else '#6be4de' if j<24 else '#d6d9bf' if j<48 else '#d98b52') if active else '#224142'
        c.line(point(137,267,59,a),point(137,267,59,b),color,7)
    for t in range(13):c.radial(137,267,48 if t%4==0 else 51,54,135+t*22.5,'#74aca0')
    for index,label in enumerate(['0','40','80','120'] if fahrenheit else ['-20','0','20','40']):
        x,y=point(137,267,42,135+index*90);c.text(x,y-9,'Label',label,'ink')
    if not missing:
        angle=135+270*f;c.radial(137,267,-5,30,angle,'copper' if stale else '#ffc9fa',3);c.radial(137,267,56,63,angle,'ink',2);c.circle(137,267,4,'copper',True);c.circle(137,267,2,'#091b23',True)
        if temperature<low or temperature>high:
            tip=point(137,267,65,angle);c.line(point(137,267,59,angle-4),tip,'ink',2);c.line(point(137,267,59,angle+4),tip,'ink',2)

def render(missing=False,fahrenheit=True,stale=False,ambient=None,up=False,time='10:08',temperature=72,heart=64,steps=8432,battery=78,clock=None,suffix=None,body_battery=76,theme=1,texture=True,weather_kind='partly',weekday=4,date='Oct 1',blank=False):
    photo=theme==1 and texture and ambient is None
    c=Canvas(theme,photo)
    if ambient is not None:
        c.text(208,92+86*ambient,'Ambient',time,'#606775');return c.finish()
    if not photo:architecture(c);robotics(c);machine(c)
    calendar(c,weekday,date,blank)
    if blank:return c.finish()
    dx,dy=-5,6
    c.rect(121+dx,51+dy,17,10,'cyan',False,2);c.line((139+dx,54+dy),(139+dx,58+dy),'cyan',2)
    if not missing:c.line((125+dx,56+dy),(125+dx+int(9*battery/100),56+dy),'cyan',2)
    c.text(174+dx,42+dy,'Small','--%' if missing else f'{battery}%','pink' if battery<=15 else 'cyan')
    c.circle(235,47+dy,3,'pink',w=2);c.line((235,53+dy),(235,60+dy),'pink',2);c.line((230,55+dy),(240,55+dy),'pink',2);c.line((235,60+dy),(231,66+dy),'pink',2);c.line((235,60+dy),(239,66+dy),'pink',2);trace(c,[(246,48+dy),(242,55+dy),(247,55+dy),(243,62+dy)],'copper');c.text(280,42+dy,'Small','--' if missing else str(body_battery),'ink')
    c.text(208,77,'Time',time,'green')
    if suffix:c.text(309,179,'Label',suffix,'ink')
    temperature_gauge(c,temperature,fahrenheit,missing,stale)
    weather(c,284,228,'unknown' if missing else weather_kind,stale,up)
    c.text(284,240,'Value',('--' if missing else str(temperature))+('°F' if fahrenheit else '°C'),'ink')
    if stale:c.circle(337,252,3,'copper');c.line((335,254),(339,250),'copper')
    solar(c,up=up,missing=missing,stale=stale,clock=clock,photo=photo)
    dy=24
    trace(c,[(101,341+dy),(92,332+dy),(92,327+dy),(95,324+dy),(99,324+dy),(101,327+dy),(103,324+dy),(107,324+dy),(110,327+dy),(110,332+dy),(101,341+dy)],'pink',2)
    c.text(149,338,'Value','--' if missing else str(heart),'ink')
    c.d.ellipse(tuple(round(v*S) for v in (220,350,226,359)),outline=c.color('cyan'),width=2*S);c.d.ellipse(tuple(round(v*S) for v in (229,356,235,365)),outline=c.color('cyan'),width=2*S);c.circle(223,346,2,'cyan',w=2);c.circle(232,352,2,'cyan',w=2)
    c.text(284,338,'Label' if steps>=1000000 else 'Small' if steps>=10000 else 'Value','--' if missing else f'{steps:,}','ink')
    return c.finish()

def main():
    docs=ROOT/'docs'; docs.mkdir(exist_ok=True); face=render(); face.save(docs/'preview-416.png')
    hero=Image.new('RGB',(1200,780),'#0b111a'); d=ImageDraw.Draw(hero)
    from PIL import ImageFont
    d.text((74,50),'PRISMELIER / FOUNDRY',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',30),fill=COL['copper'])
    d.text((74,102),'The warmth of wood. The precision of an instrument.',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf',23),fill=COL['ink'])
    hero.paste(face.resize((544,544),Image.Resampling.LANCZOS),(74,174))
    d.text((686,223),'PATINA. WOOD. PRECISION.',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19),fill='#6ab8aa')
    d.text((686,264),'Polished hardwood / luminous patina\nA live circular temperature instrument\nSunday-first calendar rim / month + day\nActual material asset used by the code',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17),fill=COL['ink'],spacing=16)
    d.text((686,477),'Forerunner 265 / 416 × 416',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16),fill=COL['cyan'])
    d.text((686,533),'DESIGN RENDER\nIllustrative data, not a simulator capture',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14),fill=COL['copper'],spacing=8)
    hero.save(docs/'preview.png')
    sheet=Image.new('RGB',(416*3,468),'#0b111a');ds=ImageDraw.Draw(sheet)
    for n,(label,im) in enumerate([('Fahrenheit / sunset / illustrative data',render()),('Sunrise / aged data / high readings',render(stale=True,up=True,temperature=130,heart=199,steps=99999,battery=100,body_battery=100,time='23:59')),('Unavailable data / honest placeholders',render(missing=True))]):
        sheet.paste(im,(416*n,0));ds.text((416*n+24,438),label,fill=COL['ink'])
    sheet.save(docs/'states.png')
    render(time='12:59',date='Sep 30',weekday=3,temperature=-40,heart=220,steps=100000,battery=100,up=True,clock='11:59P',suffix='AM',body_battery=100).save(docs/'edge-case-416.png')
    import sys
    if '--refresh-studies' in sys.argv or not (docs/'themes.png').exists():
        board=Image.new('RGB',(1120,1180),'#0b111a');bd=ImageDraw.Draw(board)
        title_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',29)
        desc_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16)
        note_font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
        bd.text((40,28),'PRISMELIER / FOUR COLOR STUDIES',font=title_font,fill='#e8e3d8')
        bd.text((40,74),'Same composition. Fahrenheit. Body Battery added at the top right.',font=desc_font,fill='#a9b3be')
        for index,t in enumerate(THEMES):
            face=render(theme=index);face.save(docs/('theme-'+t['name'].lower()+'.png'))
            x=60+(index%2)*550;y=123+(index//2)*502
            bd.text((x,y),f'{index+1:02d}  '+t['name'].upper(),font=desc_font,fill='#'+t['colors']['D98B52'])
            bd.text((x,y+26),t['description'],font=note_font,fill='#a9b3be')
            board.paste(face,(x,y+61))
        bd.text((40,1142),'DESIGN RENDERS / Illustrative values, not simulator or watch screenshots',font=note_font,fill='#a9b3be')
        board.save(docs/'themes.png')
    render(date='Oct 24',weekday=6).save(docs/'calendar-saturday.png')
    for i in range(3):render(ambient=i).save(docs/f'ambient-{i}.png')
    print('Rendered design previews, NOT simulator screenshots')
if __name__=='__main__':main()
