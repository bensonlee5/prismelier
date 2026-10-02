"""Source contracts + independent forecast date/geometry boundary models.

No Monkey C/API execution is claimed. Native tests must verify Garmin's cached
forecast data, local calendar mapping, rendering and callback persistence.
"""
from datetime import datetime, timezone
import math
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo
from test_awake_refresh import method
from test_project import without_comments

ROOT = Path(__file__).resolve().parents[1]


class ForecastSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = without_comments((ROOT / 'source/PrismelierData.mc').read_text())
        cls.view = without_comments((ROOT / 'source/PrismelierView.mc').read_text())

    def test_forecast_joins_existing_minute_batch_without_hr_polling(self):
        refresh = method(self.data, 'refresh(')
        batch = refresh.split('if (force || minute != _lastRefreshMinute)', 1)[1].split('refreshHeartRate();', 1)[0]
        self.assertIn('readForecast();', batch)
        self.assertEqual(self.data.count('Weather.getDailyForecast()'), 1)
        self.assertEqual(self.data.count('readForecast();'), 1)
        self.assertNotIn('readForecast', method(self.data, 'refreshHeartRate('))
        update = method(self.view, 'onUpdate(')
        self.assertLess(update.index('if (sleeping)'), update.index('data.refresh(false);'))
        self.assertIn('data.forecastLowC == null ? "no-range" : "range"', update)
        self.assertIn('forecast.precipitationChance', self.data)

    def test_date_selection_checks_each_entry_and_never_uses_utc_day_or_index_zero(self):
        read = method(self.data, 'readForecast(')
        for fragment in ('i < forecasts.size()', 'forecast = forecasts[i]',
                         'forecast.forecastTime == null', '!isToday(forecast.forecastTime)',
                         'low != null && high != null && low <= high'):
            self.assertIn(fragment, read)
        self.assertNotIn('forecasts[0]', read)
        date = method(self.data, 'isToday(')
        self.assertIn('Gregorian.info(moment, Time.FORMAT_SHORT)', date)
        self.assertIn('day.year * 10000 + month * 100 + day.day == _localDateKey', date)
        self.assertNotIn('utcInfo', date)
        self.assertIn('_localDateKey = info.year * 10000 + month * 100 + info.day;', method(self.data, 'updateClockLabels('))

    def test_forecast_missing_stale_and_clock_rollback_fail_closed(self):
        read = method(self.data, 'readForecast(')
        for field in ('_forecastLowC', '_forecastHighC', '_forecastTime'):
            self.assertLess(read.index(field + ' = null;'), read.index('Weather.getDailyForecast()'))
        display = method(self.data, 'updateForecastDisplay(')
        self.assertLess(display.index('forecastLowC = null;'), display.index('if ('))
        self.assertLess(display.index('forecastHighC = null;'), display.index('if ('))
        for guard in ('_weatherAt == null', 'nowSeconds < _weatherAt',
                      'nowSeconds - _weatherAt >= WEATHER_STALE_SECONDS',
                      '_forecastTime == null', '!isToday(_forecastTime)'):
            self.assertIn(guard, display)
        self.assertNotIn('_forecastTime.value()', self.data)  # validity date is not issuance age
        refresh = method(self.data, 'refresh(')
        self.assertGreater(refresh.index('updateForecastDisplay(seconds);'), refresh.index('updateWeatherDisplay(seconds);'))

    def test_thick_range_reuses_geometry_retains_scale_and_needle_without_new_numbers(self):
        draw = method(self.view, 'drawForecastRange(')
        self.assertIn('low * 9.0 / 5.0 + 32.0', draw)
        self.assertIn('high * 9.0 / 5.0 + 32.0', draw)
        self.assertIn('low == null || high == null || !(low <= high)', draw)
        self.assertIn('if (to <= from) { continue; }', draw)
        self.assertIn('bandY[j] + dy * to, copper, 9)', draw)
        self.assertIn('low == high && low >= dialLow && high <= dialHigh', draw)
        self.assertIn('if (low < dialLow)', draw)
        self.assertIn('if (high > dialHigh)', draw)
        for forbidden in ('text(', '.format(', 'point(', 'Math.', 'getDailyForecast', 'new '):
            self.assertNotIn(forbidden, draw)
        dial = method(self.view, 'drawTemperature(')
        self.assertIn('bandY[j + 1], 0x224142, 3)', dial)
        self.assertIn('["0", "40", "80", "120"]', dial)
        self.assertLess(dial.index('drawForecastRange(dc,'), dial.index('var needleAngle'))
        self.assertIn('drawWeather(dc, 284, 228, data.weatherKind);', dial)
        self.assertIn('drawSolar(dc);', dial)

    def test_selected_vertical_rail_distinguishes_unavailable_zero_and_full(self):
        draw = method(self.view, 'drawWeatherRail(')
        self.assertIn('dc.fillRectangle(x - 2.5, 244, 5, 34);', draw)
        self.assertIn('if (value != null)', draw)
        self.assertIn('34.0 * clamp(value, 0, 100) / 100.0', draw)
        self.assertIn('if (height > 0)', draw)
        self.assertIn('dc.fillRectangle(x - 2.5, 278 - height, 5, height)', draw)
        self.assertIn('stroke(dc, x - 4, 278 - height, x + 4, 278 - height, ink, 1)', draw)
        self.assertIn('value == null ? "--"', draw)
        self.assertIn('stroke(dc, x - 3, 257, x + 3, 265, muted, 1)', draw)


class ForecastBoundaryModels(unittest.TestCase):
    def test_local_date_selection_across_utc_midnight_year_and_dst(self):
        # Independent calendar oracle: local date, not seconds / 86400 or UTC day.
        cases = [
            ('America/Los_Angeles', '2026-10-02T01:00:00+00:00', '2026-10-01T20:00:00+00:00', True),
            ('America/Los_Angeles', '2026-10-02T01:00:00+00:00', '2026-10-02T20:00:00+00:00', False),
            ('Asia/Tokyo', '2026-12-31T16:00:00+00:00', '2027-01-01T01:00:00+00:00', True),
            ('America/New_York', '2026-11-01T05:30:00+00:00', '2026-11-01T06:30:00+00:00', True),
            ('America/New_York', '2026-03-08T06:30:00+00:00', '2026-03-08T07:30:00+00:00', True),
        ]
        for zone, now, valid, expected in cases:
            tz = ZoneInfo(zone)
            self.assertEqual(datetime.fromisoformat(now).astimezone(tz).date() ==
                             datetime.fromisoformat(valid).astimezone(tz).date(), expected)

    def test_clipped_segments_cover_exact_interval_without_expanding_short_ranges(self):
        def clip(value): return min(72, max(0, value))
        # In native code these are segment coordinates after unit conversion.
        for low, high in [(-30, -1), (-10, 12), (0, 72), (10.01, 10.02),
                          (12, 12), (71.9, 80), (80, 90), (-10, 90)]:
            start, end = clip(low), clip(high)
            segments = [(max(j, start), min(j + 1, end)) for j in range(72)
                        if min(j + 1, end) > max(j, start)]
            self.assertAlmostEqual(sum(b-a for a,b in segments), end-start)
            if start == end:
                self.assertEqual(segments, [])
            for a,b in segments:
                self.assertTrue(0 <= a < b <= 72)
        # Celsius forecast conversion to the default Fahrenheit dial.
        for c, f in [(-40, -40), (0, 32), (10, 50), (20, 68), (30, 86), (100, 212)]:
            self.assertAlmostEqual(c * 9 / 5 + 32, f)

    def test_forecast_thickness_and_overflow_stay_inside_dial_and_away_from_labels(self):
        # Existing tick tips end at r54; 9px range at r59 leaves a 0.5px gap.
        self.assertGreater(59 - 9 / 2, 54)
        self.assertLess(59 + 9 / 2, 70)
        for angle in (135, 405):
            x,y = 133 + 70 * math.cos(math.radians(angle)), 263 + 70 * math.sin(math.radians(angle))
            self.assertTrue(62 <= x <= 212)
            self.assertTrue(192 <= y <= 342)


if __name__ == '__main__':
    unittest.main()
