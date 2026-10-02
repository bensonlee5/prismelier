"""Complete low-power group: calendar, time, corners, and burn-in bands."""
from pathlib import Path
import math
import re
import unittest
from PIL import Image, ImageChops, ImageDraw, ImageFilter
from test_project import clock_text, font_metadata, without_comments
from test_size_variants import metadata

ROOT=Path(__file__).resolve().parents[1]

class AmbientGlanceTests(unittest.TestCase):
    def test_sleep_refreshes_local_calendar_without_sensor_reads(self):
        data=(ROOT/'source/PrismelierData.mc').read_text()
        refresh=data.split('function refreshCalendar()',1)[1].split('private function',1)[0]
        self.assertIn('updateClockLabels(Time.now());',refresh)
        self.assertNotIn('readWeather',refresh)
        view=without_comments((ROOT/'source/PrismelierView.mc').read_text())
        branch=view.split('if (sleeping) {',1)[1].split('data.refresh(false);',1)[0]
        self.assertIn('data.refreshCalendar();',branch)
        for anchor in ['208, y - 24, labelFont','208, y, ambientFont','208, y + 56, smallFont',
                       '112, y - 22','304, y + 82','0x84644C','0xA09785']:
            self.assertIn(anchor,branch)
        self.assertNotIn('data.refresh(',branch)

    def test_complete_group_fits_pixel_budget_and_disjoint_bands_at_all_sizes(self):
        source=(ROOT/'source/PrismelierView.mc').read_text()
        base,step=map(int,re.search(r'var y = (\d+) \+ slot \* (\d+)',source).groups())
        days='SUNDAY MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY'.split()+['--']
        dates=[f'{m} {d}' for m in 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split() for d in range(1,32)]+['--']
        times=sorted(set(clock_text(m,mode) for m in range(1440) for mode in (True,False)))
        for size in (360,390,416,454):
            ratio=size/416
            height=math.ceil(112*ratio)+6
            group=Image.new('L',(size,height))
            peak=0
            for name,values,offset in [('Label',days,0),('Ambient',times,24),('Small',dates,80)]:
                meta=font_metadata(name) if size==416 else metadata(size,name)
                atlas=Image.open(ROOT/('resources' if size==416 else f'packaging/variants/{size}')/f'fonts/{name}.png').convert('L')
                union=Image.new('L',group.size);component_peak=0
                for value in values:
                    mask=Image.new('L',group.size)
                    advance=sum(meta['glyphs'][ord(c)]['xadvance'] for c in value)
                    for rounding in (math.floor,math.ceil):
                        x=(size-advance)/2
                        for c in value:
                            g=meta['glyphs'][ord(c)]
                            glyph=atlas.crop((g['x'],g['y'],g['x']+g['width'],g['y']+g['height']))
                            # Lighten overlapping floor/ceil positions, never erase prior ink.
                            layer=Image.new('L',group.size)
                            layer.paste(glyph,(rounding(x+g['xoffset']),rounding(offset*ratio)+g['yoffset']+2))
                            mask=ImageChops.lighter(mask,layer);x+=g['xadvance']
                    mask=mask.point(lambda p:255 if p else 0).filter(ImageFilter.MaxFilter(3))
                    component_peak=max(component_peak,sum(mask.histogram()[1:]));union=ImageChops.lighter(union,mask)
                peak+=component_peak;group=ImageChops.lighter(group,union)
            corners=Image.new('L',group.size);draw=ImageDraw.Draw(corners)
            for x,dx in [(112,10),(304,-10)]:
                for y,dy in [(2,10),(106,-10)]:
                    draw.line([(round((x+dx)*ratio),round(y*ratio)+2),(round(x*ratio),round(y*ratio)+2),(round(x*ratio),round((y+dy)*ratio)+2)],fill=255,width=max(1,round(ratio)))
            corners=corners.filter(ImageFilter.MaxFilter(3));peak+=sum(corners.histogram()[1:]);group=ImageChops.lighter(group,corners)
            self.assertLess(peak/(math.pi*(size/2)**2),.10)
            bands=[]
            for slot in range(3):
                screen=Image.new('L',(size,size));screen.paste(group,(0,math.floor((base+slot*step-24)*ratio)-2))
                self.assertEqual(sum(screen.histogram()[1:]),sum(group.histogram()[1:]))
                b=screen.getbbox()
                for x in (b[0],b[2]-1):
                    for y in (b[1],b[3]-1):
                        self.assertLess((x+.5-size/2)**2+(y+.5-size/2)**2,(size/2)**2)
                bands.append(screen)
            for i in range(3):
                for j in range(i+1,3):self.assertIsNone(ImageChops.multiply(bands[i],bands[j]).getbbox(),(size,i,j))
            print(f'{size}px complete glance: conservative peak {peak/(math.pi*(size/2)**2):.2%}; three disjoint bands')
