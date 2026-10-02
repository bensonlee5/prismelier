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
        self.assertLess(update.index('data.refresh(false);'), update.index('displayedHeartRate == data.heartRate'))

    def test_lifecycle_events_invalidate_retained_frame(self):
        for name in ('onLayout(', 'reloadSettings(', 'onShow(', 'onHide(', 'onEnterSleep(', 'onExitSleep('):
            self.assertIn('frameValid = false;', method(self.view, name), name)
        update = method(self.view, 'onUpdate(')
        for key in ('Time.now().value() / 60', 'data.dateLabel', 'data.solarTime',
                    'data.solarLabel', 'data.weatherLabel', 'data.is24Hour()', 'data.isFahrenheit()'):
            self.assertIn(key, update)
        self.assertLess(update.index('frameValid = false;', update.index('data.refresh(false);')),
                        update.index('dc.drawBitmap'))
        self.assertGreater(update.index('frameValid = true;'), update.index('drawVitals(dc);'))

    def test_hr_path_restores_only_bounded_area_and_resets_clip_on_failure(self):
        update = method(self.view, 'onUpdate(')
        fast = update.split('if (frameValid && frameKey.equals(key))', 1)[1].split('frameValid = false;', 1)[0]
        self.assertIn('if (displayedHeartRate == data.heartRate) { return; }', fast)
        self.assertIn('if (redrawHeartRate(dc))', fast)
        repaint = method(self.view, 'redrawHeartRate(')
        self.assertLess(repaint.index('dc.setClip('), repaint.index('dc.drawBitmap'))
        self.assertEqual(repaint.count('dc.clearClip();'), 2)  # success and exception
        self.assertIn('dc.fillRectangle(114, 333, 71, 27);', repaint)
        for forbidden in ('dc.clear();', 'drawTemperature(', 'drawArchitecture(', 'data.refresh(', 'WatchUi.loadResource('):
            self.assertNotIn(forbidden, repaint)
        self.assertIn('dc.clearClip();', method(self.view, 'onUpdate(').split('if (sleeping)', 1)[0])

    def test_hr_dirty_rectangle_contains_all_old_and_new_glyph_ink(self):
        # Actual BMFont offsets/widths: changing 100 -> 99 -> -- must erase
        # every old glyph, with no need to redraw the neighboring heart/steps.
        clip = (114, 333, 185, 360)
        for value in ['--'] + [str(n) for n in range(1, 1000)]:
            for x0, y0, x1, y1 in bounds('Value', value, 149, 329):
                self.assertGreaterEqual(x0, clip[0], value)
                self.assertGreaterEqual(y0, clip[1], value)
                self.assertLessEqual(x1, clip[2], value)
                self.assertLessEqual(y1, clip[3], value)
        self.assertLess(71 * 27 / (416 * 416), 0.012)
        self.assertGreater(clip[0], 111)  # heart's rightmost ink + outline
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
