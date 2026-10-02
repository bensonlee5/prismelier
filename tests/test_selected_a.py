"""Selected-A geometry and source-drawing fixture checks, not Garmin execution."""
from pathlib import Path
import json
import math
import shutil
import sys
import unittest
from test_project import font_metadata
from test_layout_revision import bounds

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
try:
    from render_preview import commands
except ImportError:
    commands = None


class SelectedAssetTests(unittest.TestCase):
    def test_gauge_bitmap_font_sizes_and_baselines_match_reference(self):
        spec=json.loads((ROOT/'docs/design/selected-a.json').read_text())
        for name,base in [('Gauge',9),('GaugeScale',8)]:
            self.assertEqual(font_metadata(name)['common']['base'],base)
        self.assertEqual(spec['temperatureDial']['center'],[133,263])
        for value in ['RH','--%']+[str(n)+'%' for n in range(101)]:
            for center in (42,377):
                for x0,y0,x1,y1 in bounds('GaugeScale' if value=='100%' else 'Gauge',value,center,293 if value=='100%' else 292):
                    for x in (x0,x1):
                        for y in (y0,y1):
                            self.assertLess(math.hypot(x-208,y-208),204,(value,center,x,y))
        for value,top in [('100',231),('0',281)]:
            for center in (42,377):
                for x0,y0,x1,y1 in bounds('GaugeScale',value,center,top):
                    self.assertLessEqual(x1-x0,16)
                    self.assertLessEqual(y1,top+8)


@unittest.skipUnless(commands is not None and shutil.which('node'), 'Pillow and Node required for source-drawing fixtures')
class SelectedDrawingTests(unittest.TestCase):
    def test_zero_and_full_rails_have_exact_marker_positions_and_independent_colors(self):
        calls=commands({'humidity':0,'precipitationChance':100})
        markers=[c for c in calls if c['name']=='drawLine' and c['args'][0] in (38,373)
                 and c['args'][2]-c['args'][0]==8 and c['args'][1]==c['args'][3]]
        self.assertEqual([c['args'] for c in markers],[[38,278,46,278],[373,244,381,244]])
        fills=[c for c in calls if c['name']=='fillRectangle' and c['args'][2:]==[5,34]]
        self.assertTrue(any(c['args']==[374.5,244,5,34] and c['foreground']==0xC68B61 for c in fills))
        self.assertFalse(any(c['args'][0]==39.5 and c['foreground']==0xB1CCC0 for c in fills))

    def test_missing_rails_show_placeholders_without_zero_markers(self):
        calls=commands({'humidity':None,'precipitationChance':None})
        placeholders=[c for c in calls if c['name']=='drawText' and c['args'][3]=='--%']
        self.assertEqual([c['args'][:2] for c in placeholders],[[42,292],[377,292]])
        self.assertFalse(any(c['name']=='drawLine' and c['args'] in ([38,278,46,278],[373,278,381,278]) for c in calls))

    def test_dial_hub_and_vitals_use_selected_centers_and_origins(self):
        calls=commands({})
        self.assertTrue(any(c['name']=='fillCircle' and c['args']==[133,263,4] for c in calls))
        for x,value in [(149,'64'),(284,'8,432')]:
            text=next(c for c in calls if c['name']=='drawText' and c['args'][3]==value)
            self.assertEqual(text['args'][:2],[x,339])
        self.assertTrue(any(c['name']=='drawText' and c['args'][3]=='PARTLY CLOUDY' for c in calls))
        self.assertTrue(any(c['name']=='drawText' and c['args'][:2]==[280,48] and c['args'][3]=='76' for c in calls))

    def test_hr_only_update_restores_translated_region_without_weather_or_texture_redraw_outside_clip(self):
        calls=commands({'heartRate':100},update={'heartRate':99})
        self.assertEqual([c['name'] for c in calls],['drawBitmap','drawText'])
        self.assertTrue(all(c['clip']==[114,343,71,27] for c in calls))
        self.assertEqual(calls[-1]['args'][:4],[149,339,'Value','99'])
        self.assertEqual(commands({'heartRate':100},update={'heartRate':100}),[])

    def test_aod_has_only_clock_and_wake_restores_full_selected_face(self):
        sleeping=commands({},action='sleep')
        self.assertEqual([c['name'] for c in sleeping],['clear','drawText'])
        self.assertEqual(sleeping[-1]['args'][2],'Ambient')
        waking=commands({},action='wake')
        self.assertTrue(any(c['name']=='drawBitmap' for c in waking))
        self.assertTrue(any(c['name']=='drawText' and c['args'][3]=='RH' for c in waking))

    def test_missing_inverted_and_equal_forecast_do_not_invent_arc(self):
        for fixture in [{'forecastLowC':None},{'forecastLowC':30,'forecastHighC':10},
                        {'forecastLowC':20,'forecastHighC':20}]:
            calls=commands(fixture)
            self.assertFalse(any(c['name']=='drawLine' and c['pen']==9 for c in calls))
        self.assertTrue(any(c['name']=='drawLine' and c['pen']==9 for c in commands({})))


if __name__=='__main__':
    unittest.main()
