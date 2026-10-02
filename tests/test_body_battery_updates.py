"""Lifecycle/data source regression guards; not native Monkey C execution."""
from pathlib import Path
import unittest
from test_awake_refresh import method
from test_project import without_comments
from test_layout_revision import bounds

ROOT = Path(__file__).resolve().parents[1]


class BodyBatteryUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = without_comments((ROOT/'source/PrismelierData.mc').read_text())
        cls.view = without_comments((ROOT/'source/PrismelierView.mc').read_text())
        cls.app = without_comments((ROOT/'source/PrismelierApp.mc').read_text())

    def test_subscriptions_are_awake_only_and_stopped_on_hide_sleep_exit(self):
        for name in ('onShow(', 'onExitSleep('):
            self.assertIn('data.startBodyBatteryUpdates();', method(self.view, name))
        for name in ('onHide(', 'onEnterSleep('):
            self.assertIn('data.stopBodyBatteryUpdates();', method(self.view, name))
        self.assertIn('view.data.stopBodyBatteryUpdates();', method(self.app, 'onStop('))
        start = method(self.data, 'startBodyBatteryUpdates(')
        self.assertIn('if (_bodyBatteryAwake) { return; }', start)
        self.assertIn('new Complications.Id(Complications.COMPLICATION_TYPE_BODY_BATTERY)', start)
        self.assertLess(start.index('registerComplicationChangeCallback'), start.index('subscribeToUpdates'))
        stop = method(self.data, 'stopBodyBatteryUpdates(')
        self.assertIn('_bodyBatteryAwake = false;', stop)
        self.assertIn('Complications.unsubscribeFromUpdates(_bodyBatteryId)', stop)
        self.assertIn('Complications.registerComplicationChangeCallback(null)', stop)

    def test_change_notifications_coalesce_without_extra_awake_or_aod_callbacks(self):
        callback = method(self.data, 'onBodyBatteryChanged(')
        self.assertIn('_bodyBatteryAwake && id.getType() == Complications.COMPLICATION_TYPE_BODY_BATTERY', callback)
        self.assertIn('_bodyBatteryDirty = true;', callback)
        for forbidden in ('getComplication(', 'getBodyBatteryHistory(', 'requestUpdate(', 'Timer'):
            self.assertNotIn(forbidden, callback)
        read = method(self.data, 'refreshBodyBattery(')
        self.assertIn('if (!_bodyBatteryAwake) { return; }', read)
        self.assertIn('if (_bodyBatteryDirty || force || minute != _lastBodyBatteryMinute)', read)
        self.assertLess(read.index('_currentBodyBattery = null;'), read.index('getComplication('))
        self.assertIn('current instanceof Lang.Number && current >= 0 && current <= 100', read)
        self.assertIn('_currentBodyBattery != null ? _currentBodyBattery : _historyBodyBattery', read)
        self.assertNotIn('_bodyBatteryAt = nowSeconds', read)  # no invented timestamp

    def test_history_fallback_retains_original_timestamp_and_expires(self):
        history = method(self.data, 'readBodyBatteryHistory(')
        for fragment in ('new Time.Duration(BODY_BATTERY_MAX_AGE_SECONDS)',
                         'SensorHistory.ORDER_NEWEST_FIRST', 'age >= 0',
                         'sample.data >= 0', 'sample.data <= 100',
                         '_bodyBatteryAt = sample.when.value();'):
            self.assertIn(fragment, history)
        self.assertIn('const BODY_BATTERY_MAX_AGE_SECONDS = 900;', self.data)
        read = method(self.data, 'refreshBodyBattery(')
        self.assertLess(read.index('nowSeconds - _bodyBatteryAt > BODY_BATTERY_MAX_AGE_SECONDS'), read.index('bodyBattery ='))
        refresh = method(self.data, 'refresh(')
        self.assertEqual(refresh.count('readBodyBatteryHistory(seconds);'), 1)
        self.assertGreater(refresh.index('readBodyBatteryHistory(seconds);'), refresh.index('if (force || minute !='))

    def test_restored_score_is_separate_from_charge_and_fits_original_pocket(self):
        draw = method(self.view, 'drawBodyBattery(')
        self.assertIn('data.bodyBattery == null ? "--" : data.bodyBattery.format("%d")', draw)
        self.assertNotIn('"%"', draw)
        self.assertNotIn('data.battery', draw)
        update = method(self.view, 'onUpdate(')
        self.assertIn('drawBattery(dc);', update)
        self.assertIn('drawBodyBattery(dc);', update)
        for reading in ['--'] + [str(n) for n in range(101)]:
            for x0,y0,x1,y1 in bounds('Small', reading, 280, 48):
                self.assertGreaterEqual(x0, 251)
                self.assertLessEqual(x1, 309)
                self.assertGreaterEqual(y0, 50)
                self.assertLessEqual(y1, 79)

    def test_daily_rain_is_independent_of_temperature_bounds_and_age_gated(self):
        read = method(self.data, 'readForecast(')
        self.assertIn('forecast.precipitationChance', read)
        self.assertIn('chance != null && chance >= 0 && chance <= 100', read)
        self.assertLess(read.index('!isToday(forecast.forecastTime)'), read.index('forecast.precipitationChance'))
        self.assertNotIn('continue;', read.split('var low =', 1)[1])
        self.assertIn('_forecastPrecipitation = null;', read)
        display = method(self.data, 'updateForecastDisplay(')
        self.assertLess(display.index('precipitationChance = null;'), display.index('if ('))
        self.assertLess(display.index('WEATHER_STALE_SECONDS'), display.index('precipitationChance = _forecastPrecipitation'))
        self.assertNotIn('wx.precipitationChance', self.data)

    def test_selected_paired_rails_draw_independent_fields(self):
        rails = method(self.view, 'drawWeatherRails(')
        self.assertIn('drawWeatherRail(dc, 42, data.humidity, cyan);', rails)
        self.assertIn('drawWeatherRail(dc, 376, data.precipitationChance, copper);', rails)
        update = method(self.view, 'onUpdate(')
        self.assertIn('drawWeatherRails(dc);', update)
        self.assertLess(update.index('if (sleeping)'), update.index('drawWeatherRails(dc);'))


if __name__ == '__main__':
    unittest.main()
