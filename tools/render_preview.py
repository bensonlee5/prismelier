#!/usr/bin/env python3
"""Render PrismelierView's drawing commands with fixture data (NOT Garmin runtime).

Executes the view's JavaScript-compatible drawing subset through Node, then
rasterizes commands with Pillow and the committed BMFont glyphs. Sensor APIs,
font/line rasterization, firmware and memory behavior are not simulated.
"""
import argparse
import json
from pathlib import Path
import re
import shlex
import subprocess
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]


def commands(fixture, update=None, action=None):
    source = (ROOT/'source/PrismelierView.mc').read_text()
    source = re.sub(r'//[^\n]*|/\*.*?\*/', '', source, flags=re.S)
    source = source.replace('.length()', '.length')
    # Resolve the one parameter that shadows a view member before JS with().
    source = source.replace('paint(dc, foreground, background)', 'paint(dc, foreground, bg)')
    source = source.replace('dc.setColor(c, background)', 'dc.setColor(c, bg)')
    fields = source.split('function initialize()', 1)[0].split('{', 1)[1]
    fields = re.sub(r'\bvar\s+(\w+)\s*;', r'view.\1 = null;', fields)
    fields = re.sub(r'\bvar\s+(\w+)\s*=', r'view.\1 =', fields)
    methods = []
    for match in re.finditer(r'function (\w+)\(([^)]*)\)\s*\{', source):
        depth, end = 1, match.end()
        while depth:
            depth += (source[end] == '{') - (source[end] == '}')
            end += 1
        methods.append('view.'+match[1]+' = function('+match[2]+'){ with(view){'+source[match.end():end-1]+'}};')
    js = r'''
Number.prototype.toNumber=function(){return Math.trunc(this);};
Number.prototype.toFloat=function(){return Number(this);};
Number.prototype.format=function(f){let s=String(Math.trunc(this));return f==='%02d'?s.padStart(2,'0'):f==='%03d'?s.padStart(3,'0'):s;};
String.prototype.equals=function(s){return String(this)===String(s);};
String.prototype.find=function(s){const i=this.indexOf(s);return i<0?null:i;};
Array.prototype.add=Array.prototype.push;
Array.prototype.size=function(){return this.length;};
const Graphics={COLOR_BLACK:0,COLOR_TRANSPARENT:-1,TEXT_JUSTIFY_CENTER:1};
const WatchFace={initialize(){}};
const WatchUi={loadResource:r=>r,requestUpdate(){}};
const Rez={Fonts:{Time:'Time',Value:'Value',Small:'Small',Label:'Label',Ambient:'Ambient',Gauge:'Gauge',GaugeScale:'GaugeScale'},Drawables:{FoundryBackground:'background'}};
const System={getClockTime:()=>({hour:fixture.hour??10,min:fixture.minute??8})};
const Time={now:()=>({value:()=>1790935680})};
const PrismelierPalette={color:(c,t)=> c===0||c===0x606775?c:parseInt(palettes[t].colors[c.toString(16).toUpperCase().padStart(6,'0')]||c.toString(16),16)};
function PrismelierData(){return Object.assign({palette:1,temperatureC:(72-32)*5/9,forecastLowC:(58-32)*5/9,forecastHighC:(79-32)*5/9,weatherStale:false,weatherLabel:'PARTLY CLOUDY',weatherKind:'partly',humidity:62,precipitationChance:30,bodyBattery:76,battery:78,heartRate:64,steps:8432,dateLabel:'Oct 2',glanceDateLabel:'OCT 02',weekdayIndex:5,solarLabel:'SUNSET',solarTime:'6:42 PM',is24Hour:()=>!!fixture.hours24,isFahrenheit:()=>!fixture.celsius,formatTime:()=>fixture.time||'10:08',refresh(){},refreshCalendar(){},loadSettings(){},startBodyBatteryUpdates(){},stopBodyBatteryUpdates(){}},fixture);}
const calls=[];let foreground=0,background=0,pen=1,clip=null;
const dc={setColor(f,b){foreground=f;background=b},setPenWidth(w){pen=w},setAntiAlias(){},setClip(...a){clip=a},clearClip(){clip=null}};
for(const name of ['clear','drawBitmap','drawCircle','drawEllipse','drawLine','drawRectangle','drawRoundedRectangle','drawText','fillCircle','fillPolygon','fillRectangle','fillRoundedRectangle'])dc[name]=(...args)=>calls.push({name,args,foreground,background,pen,clip});
const view={};
'''
    js = 'const fixture='+json.dumps(fixture)+';const palettes='+ (ROOT/'resources/themes.json').read_text()+';\n'+js+fields+'\n'+'\n'.join(methods)+'\nview.initialize();view.onLayout(dc);view.onShow();view.onUpdate(dc);'
    if update is not None:
        js += 'calls.length=0;Object.assign(view.data,'+json.dumps(update)+');view.onUpdate(dc);'
    if action == 'sleep':
        js += 'calls.length=0;view.onEnterSleep();view.onUpdate(dc);'
    if action == 'wake':
        js += 'view.onEnterSleep();view.onUpdate(dc);calls.length=0;view.onExitSleep();view.onUpdate(dc);'
    js += 'console.log(JSON.stringify(calls));'
    result = subprocess.run(['node'], input=js, text=True, capture_output=True, check=False)
    if result.returncode: raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def font(name):
    glyphs={};page=None
    for line in (ROOT/f'resources/fonts/{name}.fnt').read_text().splitlines():
        parts=shlex.split(line)
        d=dict(p.split('=',1) for p in parts[1:])
        if parts[0]=='page':page=Image.open(ROOT/'resources/fonts'/d['file']).convert('L')
        if parts[0]=='char':glyphs[int(d['id'])]={k:int(v) for k,v in d.items()}
    return page,glyphs


def render(fixture):
    scale=3
    canvas=Image.new('RGB',(416*scale,416*scale))
    fonts={}
    def xy(v):return tuple(n*scale for n in v)
    def color(n):return '#%06x'%n
    for call in commands(fixture):
        name,a,c,w=call['name'],call['args'],color(call['foreground']),max(1,round(call['pen']*scale))
        draw=ImageDraw.Draw(canvas)
        if call['clip'] is not None:raise ValueError('Initial full-frame preview unexpectedly clipped')
        if name=='clear':draw.rectangle((0,0,416*scale,416*scale),fill=color(call['background']))
        elif name=='drawBitmap':canvas.paste(Image.open(ROOT/'resources/textures/foundry-background-indexed.png').convert('RGB').resize(canvas.size,Image.Resampling.LANCZOS),(0,0))
        elif name in ('fillCircle','drawCircle'):
            x,y,r=a;draw.ellipse(xy((x-r,y-r,x+r,y+r)),fill=c if name=='fillCircle' else None,outline=c,width=w)
        elif name=='drawEllipse':
            x,y,ww,h=a;draw.ellipse(xy((x,y,x+ww,y+h)),outline=c,width=w)
        elif name=='drawLine':draw.line(xy(a),fill=c,width=w)
        elif name=='fillPolygon':draw.polygon([xy(p) for p in a[0]],fill=c)
        elif name in ('drawRectangle','fillRectangle','drawRoundedRectangle','fillRoundedRectangle'):
            x,y,ww,h=a[:4];box=xy((x,y,x+ww,y+h));fill=c if name.startswith('fill') else None
            if 'Rounded' in name:draw.rounded_rectangle(box,radius=a[4]*scale,fill=fill,outline=c,width=w)
            else:draw.rectangle(box,fill=fill,outline=c,width=w)
        elif name=='drawText':
            x,y,fontname,text,_=a
            if fontname not in fonts:fonts[fontname]=font(fontname)
            page,glyphs=fonts[fontname]
            x-=sum(glyphs[ord(ch)]['xadvance'] for ch in text)/2
            for ch in text:
                g=glyphs[ord(ch)]
                mask=page.crop((g['x'],g['y'],g['x']+g['width'],g['y']+g['height']))
                mask=mask.resize((g['width']*scale,g['height']*scale),Image.Resampling.NEAREST)
                canvas.paste(c,(round((x+g['xoffset'])*scale),round((y+g['yoffset'])*scale)),mask)
                x+=g['xadvance']
        else:raise ValueError(name)
    return canvas.resize((416,416),Image.Resampling.LANCZOS)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/screenshots/selected-a-source-preview.png')
    parser.add_argument('--fixture',type=Path)
    args=parser.parse_args()
    fixture=json.loads(args.fixture.read_text()) if args.fixture else {}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    render(fixture).save(args.output)
    print(args.output)
