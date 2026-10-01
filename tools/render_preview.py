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
    x,y=240,277 if photo else 269;color='#777f70' if missing else '#27645d' if up else '#a04d30';suny=y-4 if up else y
    for a in range(180,360,15):c.line(point(x,suny,8,a),point(x,suny,8,a+15),color,2)
    c.line((x-14,y),(x+12,y),color,2)
    for a in (220,270,320):c.radial(x,suny,11,14,a,color,2)
    if not missing:
        tipy=y-12 if up else y+10;basey=tipy+5 if up else tipy-5
        c.line((x+16,y-12 if up else y+1),(x+16,y-3 if up else y+10),color,2);c.line((x+12,basey),(x+16,tipy),color,2);c.line((x+20,basey),(x+16,tipy),color,2)
    c.text(302,255 if photo else 250,'Small',clock or ('--:--' if missing else '06:48' if up else '18:42'),'#183b3b')
    if stale:c.circle(345,285 if photo else 278,3,'copper')
def trace(c,points,color,w=1):
    for a,b in zip(points,points[1:]):c.line(a,b,color,w)
def junction(c,x,y,color):c.circle(x,y,3,color);c.circle(x,y,1,color,True)
def architecture(c):
    c.polygon([(121,25),(283,25),(350,87),(350,168),(67,168),(67,87)],'#071214')
    paths=[([(111,39),(137,19),(279,19),(301,37)],'#3d3433'), ([(118,43),(141,25),(275,25),(294,43)],'#175452'), ([(137,48),(151,34),(264,34),(280,50)],'#224142'), ([(100,48),(65,81),(65,108),(53,120),(53,143)],'#6e4b3a'), ([(109,53),(74,84),(74,103),(62,115)],'#2f625c'), ([(303,49),(342,84),(342,105),(356,119),(356,143)],'#335657'), ([(309,42),(350,79),(350,102),(365,117)],'#644154')]
    for points,color in paths:trace(c,points,color)
    for x,y,color in [(53,145,'#916b49'),(62,116,'#34877d'),(356,145,'#4f958b'),(366,119,'#86557a')]:junction(c,x,y,color)
    c.rect(104,39,106,31,'#102226',True,7);c.line((114,39),(200,39),'#3c6260')
    for b in range(5):c.line((184+b*7,29),(184+b*7,34),'#8b6544')
    c.rect(219,39,91,31,'#102226',True,7);c.line((228,39),(300,39),'#3c6260');junction(c,214,55,'#724060');trace(c,[(210,55),(219,55)],'#724060')
    for points,color in [([(34,129),(23,157),(23,252),(32,274)],'#22433f'), ([(29,161),(29,236)],'#503949'), ([(383,130),(393,163),(393,249),(384,272)],'#4d3c2e'), ([(387,174),(387,223),(381,230)],'#284d4d')]:trace(c,points,color)
    for n in range(4):
        c.line((20,187+n*7),(28,187+n*7),'#326960');c.line((388,240+n*6),(394,240+n*6),'#6f494d')
    c.polygon([(71,312),(345,312),(335,352),(292,374),(123,374),(82,352)],'#080f13')
    for points,color in [([(70,315),(76,348),(120,373),(158,373),(171,386),(203,386)],'#6b4839'), ([(78,351),(122,379),(157,379)],'#263d3d'), ([(346,315),(340,349),(299,373),(260,373),(247,386),(216,386)],'#295f5d'), ([(333,356),(297,379),(261,379)],'#69465b')]:trace(c,points,color)
    junction(c,204,386,'#a16e4c');junction(c,215,386,'#4b9d95')
    for f in range(7):c.line((175+f*11,364),(181+f*11,364),'#334945')
    trace(c,[(92,360),(121,367),(150,367)],'#243f42');trace(c,[(324,361),(295,367),(270,367)],'#3f314c');screw(c,90,348,'#75513d');screw(c,326,348,'#365e59')

def robotics(c):
    for x in (44,357):
        c.rect(x,116,15,33,'#080f13',True,2);c.rect(x,116,15,33,'#334945',False,2)
        for pin in range(5):c.rect(x+4,120+pin*5,7,2,'copper')
    for ribbon in range(4):
        trace(c,[(113+ribbon*4,68),(113+ribbon*4,74),(98+ribbon*4,87)],'#8b6544')
        trace(c,[(285+ribbon*4,68),(285+ribbon*4,74),(300+ribbon*4,87)],'#335657')
    for x in (52,335):c.rect(x,170,29,27,'#102226',True,4);c.rect(x,170,29,27,'#6b4839',False,4)
    for pin in range(8):
        c.line((179+pin*8,348),(179+pin*8,355),'#8b6544',2);c.line((179+pin*8,373),(179+pin*8,380),'#8b6544',2)
    for row in range(3):
        c.line((167,357+row*6),(175,357+row*6),'#335657',2);c.line((241,357+row*6),(249,357+row*6),'#335657',2)
    c.rect(173,352,70,24,'#080f13',True,3);c.rect(173,352,70,24,'#6b4839',False,3);c.rect(189,357,38,14,'#224142');c.rect(189,357,38,14,'#3c6260',False)
    for core in range(3):c.rect(193+core*11,360,7,8,'#3c6260',False)
    c.circle(179,357,1,'copper',True)

def render(missing=False,fahrenheit=True,stale=False,ambient=None,up=False,time='10:08',temperature=72,heart=64,steps=8432,battery=78,clock=None,suffix=None,body_battery=76,theme=1,texture=True,weather_kind='partly'):
    photo=theme==1 and texture and ambient is None
    c=Canvas(theme,photo)
    if ambient is not None:
        c.text(208,92+86*ambient,'Ambient',time,'#606775');return c.finish()
    if not photo:
        architecture(c);robotics(c)
        c.rect(45,184,326,110,'panel',True,17);c.rect(45,184,326,110,'#344741',False,17)
        for x in (42,374):
            c.line((x,207),(x,262),'#5d3527',7);c.line((x-1,207),(x-1,262),'copper',2)
            for k in range(6):c.line((x-5,214+k*8),(x+5,214+k*8),'#b56942',2)
        gear(c,67,184,11,'pink');gear(c,349,184,11,'cyan');screw(c,59,282);screw(c,357,282)
        c.polygon([(224,249),(344,249),(352,256),(347,286),(221,286),(217,278)],'#050e12');c.polygon([(224,246),(344,246),(352,253),(347,283),(221,283),(217,275)],'#d6d9bf');c.line((227,248),(341,248),'#f5f5db');c.line((224,246),(217,275),'copper',2);c.line((217,275),(221,283),'copper',2);c.line((81,288),(101,288),'#74aca0')
        c.line((84,288),(105,300),'#805745',2);c.line((105,300),(162,300),'#805745',2);c.line((253,300),(310,300),'#487b72',2);c.line((310,300),(331,288),'#487b72',2);screw(c,162,300,'pink');screw(c,253,300,'cyan')
    dx,dy=(-5,2) if photo else(0,0)
    c.rect(121+dx,51+dy,17,10,'cyan',False,2);c.line((139+dx,54+dy),(139+dx,58+dy),'cyan',2)
    if not missing:c.line((125+dx,56+dy),(125+dx+int(9*battery/100),56+dy),'cyan',2)
    c.text(174+dx,42+dy,'Small','--%' if missing else f'{battery}%','pink' if battery<=15 else 'cyan')
    c.circle(235,47+dy,3,'pink',w=2);c.line((235,53+dy),(235,60+dy),'pink',2);c.line((230,55+dy),(240,55+dy),'pink',2);c.line((235,60+dy),(231,66+dy),'pink',2);c.line((235,60+dy),(239,66+dy),'pink',2);trace(c,[(246,48+dy),(242,55+dy),(247,55+dy),(243,62+dy)],'copper');c.text(280,42+dy,'Small','--' if missing else str(body_battery),'ink')
    c.text(208,78 if photo else 77,'Time',time,'green')
    if suffix:c.text(208,163,'Label',suffix,'ink')
    if not photo:
        c.rect(56,192,304,54,'#452744',True,10)
        for grain in range(5):c.line((71,197+grain*10),(345,199+grain*10),'#85506d' if grain%2==0 else '#5d3854')
        c.rect(56,192,304,54,'copper',False,10);c.line((71,193),(344,193),'#f2bf8c');c.line((71,245),(344,245),'#3e211e',2)
        for x,y in [(64,201),(352,201),(64,237),(352,237)]:screw(c,x,y)
        c.rect(73,209,270,19,'#091b23',True,4)
    lo,hi=(0,120) if fahrenheit else(-20,40)
    if not missing:
        start,full=(74,268) if photo else(77,262);width=int(full*max(0,min(1,(temperature-lo)/(hi-lo))))
        if width:
            c.rect(start,214,width,9,'#80665c' if stale else 'pink',True,3);c.line((start+2,215),(start+width,215),'copper' if stale else '#ffc9fa')
        c.rect(start-2+width,211,4,17,'ink')
    if not photo:
        for t in range(13):
            x=77+int(262*t/12);c.line((x,202),(x,207 if t%3==0 else 205),'copper');c.line((x,232),(x,238 if t%3==0 else 235),'copper')
    weather(c,94,272 if photo else 265,'unknown' if missing else weather_kind,stale,up)
    c.text(165,254 if photo else 247,'Value',('--' if missing else str(temperature))+('°F' if fahrenheit else '°C'),'ink')
    if stale:
        wx,wy=(72,283) if photo else (208,280);c.circle(wx,wy,3,'copper');c.line((wx-2,wy+2),(wx+2,wy-2),'copper')
    solar(c,up=up,missing=missing,stale=stale,clock=clock,photo=photo)
    dy=0
    trace(c,[(101,341+dy),(92,332+dy),(92,327+dy),(95,324+dy),(99,324+dy),(101,327+dy),(103,324+dy),(107,324+dy),(110,327+dy),(110,332+dy),(101,341+dy)],'pink',2)
    c.text(149,315+dy,'Value','--' if missing else str(heart),'ink')
    c.d.ellipse(tuple(round(v*S) for v in (220,322+dy,226,333+dy)),outline=c.color('cyan'),width=2*S);c.d.ellipse(tuple(round(v*S) for v in (229,328+dy,235,339+dy)),outline=c.color('cyan'),width=2*S);c.circle(223,318+dy,2,'cyan',w=2);c.circle(232,324+dy,2,'cyan',w=2)
    c.text(284 if photo else 288,315+dy,'Small' if steps>=10000 else 'Value','--' if missing else f'{steps:,}','ink')
    return c.finish()

def main():
    docs=ROOT/'docs'; docs.mkdir(exist_ok=True); face=render(); face.save(docs/'preview-416.png')
    hero=Image.new('RGB',(1200,780),'#0b111a'); d=ImageDraw.Draw(hero)
    from PIL import ImageFont
    d.text((74,50),'PRISMELIER / FOUNDRY',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',30),fill=COL['copper'])
    d.text((74,102),'Impossible materials. Unapologetically digital.',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf',23),fill=COL['ink'])
    hero.paste(face.resize((544,544),Image.Resampling.LANCZOS),(74,174))
    d.text((686,223),'TACTILE MATERIALS. LIVE INSTRUMENTS.',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19),fill='#6ab8aa')
    d.text((686,264),'Brushed copper and patinated circuitry\nWorn ceramic with real surface texture\nQuiet wells, live values, thin-line icons\nA static asset actually used by the code',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17),fill=COL['ink'],spacing=16)
    d.text((686,477),'Forerunner 265 / 416 × 416',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16),fill=COL['cyan'])
    d.text((686,533),'DESIGN RENDER\nIllustrative data, not a simulator capture',font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',14),fill=COL['copper'],spacing=8)
    hero.save(docs/'preview.png')
    sheet=Image.new('RGB',(416*3,468),'#0b111a');ds=ImageDraw.Draw(sheet)
    for n,(label,im) in enumerate([('Fahrenheit / sunset / illustrative data',render()),('Sunrise / aged data / high readings',render(stale=True,up=True,temperature=130,heart=199,steps=99999,battery=100,body_battery=100,time='23:59')),('Unavailable data / honest placeholders',render(missing=True))]):
        sheet.paste(im,(416*n,0));ds.text((416*n+24,438),label,fill=COL['ink'])
    sheet.save(docs/'states.png')
    render(time='12:59',temperature=-40,heart=220,steps=100000,battery=100,up=True,clock='11:59P',suffix='AM',body_battery=100).save(docs/'edge-case-416.png')
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
    for i in range(3):render(ambient=i).save(docs/f'ambient-{i}.png')
    print('Rendered design previews, NOT simulator screenshots')
if __name__=='__main__':main()
