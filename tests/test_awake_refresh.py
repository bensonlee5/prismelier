"""Regression guards for awake data/render scheduling and actual font bounds.

These inspect Monkey C source and font assets; they do not execute Garmin APIs
or prove framebuffer persistence. Native simulator/device checks remain required.
"""
from pathlib import Path
import re
import unittest
from test_project import without_comments
from test_layout_revision import bounds

ROOT = Path(__file__).resolve().parents[1]


def method(code, name):
    return code.split('function ' + name, 1)[1].split('\n    function ', 1)[0].split('\n    private function ', 1)[0]


class AwakeRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = without_comments((ROOT / 'source/PrismelierData.mc').read_text())
        cls.view = without_comments((ROOT / 'source/PrismelierView.mc').read_text())

    def test_current_hr_is_outside_minute_gate_and_after_history_expiry(self):
        refresh = method(self.data, 'refresh(')
        # Live reads must occur after the cache block closes, even within a minute.
        self.assertRegex(refresh, r'buildSolarEvents\(now, seconds\);\s*}\s*refreshHeartRate\(\);')
        self.assertLess(refresh.index('seconds - _heartRateAt >'), refresh.index('refreshHeartRate();'))
        current = method(self.data, 'refreshHeartRate(')
        self.assertLess(current.index('heartRate = _historyHeartRate;'), current.index('Activity.getActivityInfo()'))
        for guard in ('current != null', 'current > 0', 'current != ActivityMonitor.INVALID_HR_SAMPLE'):
            self.assertIn(guard, current)
        self.assertNotIn('_heartRateAt =', current)  # Never invent a sample timestamp.
        self.assertNotIn('_historyHeartRate =', current)  # Never retain untimestamped live values.
        self.assertNotIn('SensorHistory.', current)
        self.assertNotIn('Weather.', current)
        update = method(self.view, 'onUpdate(')
        self.assertLess(update.index('if (sleeping)'), update.index('data.refresh(false);'))
        self.assertLess(update.index('data.refresh(false);'), update.index('drawVitals(dc);'))

    def test_awake_updates_do_not_depend_on_retained_display_pixels(self):
        update = method(self.view, 'onUpdate(')
        awake = update.split('data.refresh(false);', 1)[1]
        self.assertNotIn('return;', awake)
        self.assertNotIn('frameValid', self.view)
        self.assertNotIn('redrawHeartRate', self.view)
        self.assertLess(awake.index('dc.clear();'), awake.index('drawVitals(dc);'))
        self.assertIn('dc.clearClip();', update.split('if (sleeping)', 1)[0])

    def test_hr_panel_contains_all_glyph_ink(self):
        # Actual BMFont ink must remain inside the lower metric panel.
        clip = (114, 343, 185, 370)
        for value in ['--'] + [str(n) for n in range(1, 1000)]:
            for x0, y0, x1, y1 in bounds('Value', value, 149, 339):
                self.assertGreaterEqual(x0, clip[0], value)
                self.assertGreaterEqual(y0, clip[1], value)
                self.assertLessEqual(x1, clip[2], value)
                self.assertLessEqual(y1, clip[3], value)
        self.assertLess(71 * 27 / (416 * 416), 0.012)
        self.assertGreaterEqual(clip[0], 114)  # heart's shifted rightmost ink + outline
        self.assertLess(clip[2], 218)    # steps' leftmost ink

    def test_humidity_missing_weather_age_guards(self):
        display = method(self.data, 'updateWeatherDisplay(')
        for invalid in ('_weatherAt == null', 'age < 0', 'age >= WEATHER_EXPIRE_SECONDS'):
            self.assertLess(display.index(invalid), display.index('humidity = _weatherHumidity;'))
        read = method(self.data, 'readWeather(')
        self.assertIn('_weatherHumidity = wx.relativeHumidity;', read)
        self.assertIn('_weatherAt = wx.observationTime == null ? null : wx.observationTime.value();', read)
        self.assertIn('_forecastPrecipitation = chance;', self.data)


if __name__ == '__main__':
    unittest.main()
