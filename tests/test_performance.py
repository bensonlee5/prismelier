"""Source guards and independent cost/cache models, not Monkey C execution.

Native timing, heap use, redraw persistence and battery drain still require the
FR265 simulator/watch. These tests prevent regression of the targeted policies.
"""
import math
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "",
                  (ROOT / "source" / name).read_text(), flags=re.S)


class PerformanceSourceTests(unittest.TestCase):
    def test_startup_and_wake_do_not_force_duplicate_reads(self):
        view = source("PrismelierView.mc")
        init = view.split("function initialize()", 1)[1].split("function onLayout", 1)[0]
        wake = view.split("function onExitSleep()", 1)[1].split("function paint", 1)[0]
        self.assertEqual(init.count("new PrismelierData()"), 1)
        self.assertNotIn("reloadSettings()", init)
        self.assertNotIn("data.refresh", init + wake)
        self.assertIn("WatchUi.requestUpdate();", wake)
        settings = view.split("function reloadSettings()", 1)[1].split("function refreshTexture", 1)[0]
        self.assertIn("data.refresh(true);", settings)
        self.assertIn("data.refresh(false);", view)

    def test_band_geometry_is_small_and_built_once(self):
        view = source("PrismelierView.mc")
        init = view.split("function initialize()", 1)[1].split("function onLayout", 1)[0]
        draw = view.split("function drawTemperature", 1)[1].split("for (var tick", 1)[0]
        self.assertIn("var j = 0; j <= 72; j += 1", init)
        self.assertIn("point(133, 263, 59, 135.0 + 270.0 * j / 72)", init)
        self.assertEqual(view.count("bandX.add("), 1)
        self.assertEqual(view.count("bandY.add("), 1)
        self.assertIn("bandX[j], bandY[j], bandX[j + 1], bandY[j + 1]", draw)
        self.assertNotIn("point(", draw)
        self.assertNotIn("BufferedBitmap", view)

    def test_solar_cache_validates_before_reuse_and_keeps_retry(self):
        code = source("PrismelierData.mc")
        solar = code.split("private function buildSolarEvents", 1)[1].split("private function addSolarEvent", 1)[0]
        for guard in ("nowSeconds < _locationAt", "nowSeconds - _locationAt >= WEATHER_EXPIRE_SECONDS",
                      "nowSeconds >= _solarBuiltAt", "nowSeconds < _solarRetryAfter",
                      "day == _solarDay", "coordinates[0] == _solarLatitude",
                      "coordinates[1] == _solarLongitude"):
            self.assertIn(guard, solar)
        self.assertLess(solar.index("nowSeconds - _locationAt"), solar.index("_location.toDegrees()"))
        self.assertLess(solar.index("coordinates[1] == _solarLongitude"), solar.index("Weather.getSunrise"))
        self.assertIn("const SOLAR_CACHE_SECONDS = 3600;", code)
        self.assertIn("const SOLAR_RETRY_SECONDS = 300;", code)
        self.assertIn("_solarBuiltAt = -1;", solar)
        self.assertLess(solar.index("nowSeconds + SOLAR_RETRY_SECONDS"), solar.index("Weather.getSunrise"))
        self.assertGreater(solar.index("nowSeconds + SOLAR_CACHE_SECONDS"), solar.index('Weather.getSunset(_location, tomorrow)'))
        failure = solar.split("catch (e)", 1)[1]
        self.assertIn("_solarEvents = [];", failure)
        self.assertIn("_solarKinds = [];", failure)
        self.assertIn("_solarRetryAfter = nowSeconds + SOLAR_RETRY_SECONDS;", failure)

    def test_no_new_timer_animation_or_sensor_activation(self):
        code = "\n".join(source(p.name) for p in (ROOT / "source").glob("*.mc"))
        for forbidden in ("Toybox.Timer", "onPartialUpdate", "requestAnimationFrame",
                          "enableLocationEvents", "enableSensorEvents", "makeWebRequest"):
            self.assertNotIn(forbidden, code)


class IndependentPerformanceModels(unittest.TestCase):
    def test_cached_points_equal_all_original_segment_endpoints(self):
        def point(degrees):
            a = degrees * math.pi / 180.0
            return 133 + math.cos(a) * 59, 263 + math.sin(a) * 59
        cached = [point(135.0 + 270.0 * j / 72) for j in range(73)]
        for j in range(72):
            self.assertEqual(cached[j], point(135.0 + 270.0 * j / 72))
            self.assertEqual(cached[j + 1], point(135.0 + 270.0 * (j + 1) / 72))
        # Logical counts only: 73 one-time points versus 144 points per frame.
        self.assertEqual(len(cached) * 2, 146)

    def test_cache_model_invalidation_boundaries(self):
        def reusable(now=1001, built=1000, retry=4600, day=86400,
                     stored_day=86400, coords=(37.0, -122.0),
                     stored_coords=(37.0, -122.0)):
            return (built >= 0 and now >= built and now < retry and
                    day == stored_day and coords == stored_coords)
        self.assertTrue(reusable())
        self.assertTrue(reusable(now=4599))
        self.assertFalse(reusable(now=4600))
        self.assertFalse(reusable(now=999))
        self.assertFalse(reusable(built=-1))
        self.assertFalse(reusable(day=172800))
        self.assertFalse(reusable(day=90000))  # Local midnight after zone change
        self.assertFalse(reusable(coords=(37.001, -122.0)))
        self.assertFalse(reusable(coords=(37.0, -122.001)))
        self.assertTrue(reusable(retry=1300, now=1299))
        self.assertFalse(reusable(retry=1300, now=1300))

    def test_gestures_within_minute_share_one_history_read(self):
        last = -1
        reads = 0
        for seconds in (600, 601, 605, 610, 620, 640, 659, 660):
            minute = seconds // 60
            if minute != last:
                reads += 1
                last = minute
        self.assertEqual(reads, 2)


if __name__ == "__main__":
    unittest.main()
