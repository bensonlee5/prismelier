"""Calendar/gauge geometry and glyph bounds, not native-device rendering."""
from pathlib import Path
import math
import re
import unittest
from test_project import font_metadata, clock_text, without_comments

ROOT = Path(__file__).resolve().parents[1]


def bounds(name, text, center, top):
    glyphs = font_metadata(name)['glyphs']
    advance = sum(glyphs[ord(c)]['xadvance'] for c in text)
    x = center - advance / 2
    boxes = []
    for c in text:
        g = glyphs[ord(c)]
        boxes.append((x + g['xoffset'], top + g['yoffset'],
                      x + g['xoffset'] + g['width'], top + g['yoffset'] + g['height']))
        x += g['xadvance']
    return boxes


class RevisionLayoutTests(unittest.TestCase):
    def inside(self, name, value, center, top, well):
        for x0,y0,x1,y1 in bounds(name,value,center,top):
            self.assertGreaterEqual(x0,well[0],(value,x0,well))
            self.assertGreaterEqual(y0,well[1],(value,y0,well))
            self.assertLessEqual(x1,well[2],(value,x1,well))
            self.assertLessEqual(y1,well[3],(value,y1,well))

    def test_all_clock_strings_fit_recessed_visor(self):
        for minute in range(1440):
            for hours24 in (False,True):
                self.inside('Time',clock_text(minute,hours24),208,77,(74,93,342,168))

    def test_month_day_lowercase_glyphs_and_plate_fit(self):
        for month in 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split():
            for day in range(1,32):
                self.inside('Small',f'{month} {day}',208,175,(166,179,250,199))

    def test_weekday_order_distinct_positions_and_safe_circle(self):
        code=(ROOT/'source/PrismelierView.mc').read_text()
        self.assertIn('["S", "M", "T", "W", "T", "F", "S"]',code)
        self.assertIn('data.weekdayIndex != null && data.weekdayIndex == i',code)
        self.assertIn('current ? 0xF2BF8C : 0x74ACA0',code)
        centers=[]
        for i,letter in enumerate('SMTWTFS'):
            angle=math.radians(210+i*20)
            x,y=208+188*math.cos(angle),208+188*math.sin(angle)
            centers.append((x,y))
            for box in bounds('Small',letter,x,y-12):
                for xx in (box[0],box[2]):
                    for yy in (box[1],box[3]):
                        self.assertLess(math.hypot(xx-208,yy-208),204)
        self.assertEqual(len(set(centers)),7)
        self.assertNotEqual(centers[0],centers[6])
        self.assertNotEqual(centers[2],centers[4])

    def test_worst_metrics_remain_inside_quiet_wells(self):
        for text in ('°F','°C'):
            self.inside('Value',text,284,240,(225,244,348,270))
        for text in ('11:59P','23:59','--:--'):
            self.inside('Small',text,307,278,(268,281,349,309))
        self.inside('Value','220',149,338,(115,343,181,367))
        for text in ('100,000','999,999'):
            self.inside('Small',text,284,338,(238,341,332,367))
        self.inside('Label','1,000,000',284,338,(238,341,332,367))

    def test_temperature_sweep_missing_and_overflow_contract(self):
        code=without_comments((ROOT/'source/PrismelierView.mc').read_text())
        gauge=code.split('function drawTemperature(dc)',1)[1].split('function drawVitals(dc)',1)[0]
        self.assertIn('var low = fahrenheit ? 0 : -20;',gauge)
        self.assertIn('var high = fahrenheit ? 120 : 40;',gauge)
        self.assertIn('var needleAngle = 135.0 + 270.0 * f;',gauge)
        self.assertIn('if (val < low || val > high)',gauge)
        self.assertIn('var active = val != null',gauge)
        self.assertIn('if (val != null)',gauge)
        self.assertNotIn('fullWidth',gauge)
        self.assertNotIn('Math.round(val)',gauge)
        self.assertNotIn('var reading',gauge)
        self.assertIn('text(dc, 284, 240, valueFont, fahrenheit ? "°F" : "°C", ink);',gauge)
        self.assertIn('["0", "40", "80", "120"]',gauge)
        self.assertIn('text(dc, 208, 77, timeFont, time, green);',code)
        preview=(ROOT/'tools/render_preview.py').read_text()
        self.assertIn("c.text(284,240,'Value','°F' if fahrenheit else '°C','ink')",preview)
        self.assertNotIn('str(temperature)',preview)
        for reading,angle in ((-40,135),(0,135),(60,270),(120,405),(130,405)):
            self.assertEqual(135+270*max(0,min(1,reading/120)),angle)
        for method in ('drawCalendar(dc);','drawTemperature(dc);'):
            update=code.split('function onUpdate(dc)',1)[1].split('function screw',1)[0]
            self.assertLess(update.index('return;'),update.index(method))


if __name__=='__main__':
    unittest.main()
