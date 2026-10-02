using Toybox.ActivityMonitor;
using Toybox.Application;
using Toybox.Lang;
using Toybox.Position;
using Toybox.SensorHistory;
using Toybox.System;
using Toybox.Time;
using Toybox.Time.Gregorian;
using Toybox.Weather;

// Cached, read-only watch-face data. No GPS activation or network requests.
// Permissions: SensorHistory; Positioning exposes weather observation position.
// https://developer.garmin.com/connect-iq/api-docs/Toybox/Weather/CurrentConditions.html
// https://developer.garmin.com/connect-iq/api-docs/Toybox/Weather.html
// https://developer.garmin.com/connect-iq/api-docs/Toybox/SensorHistory.html
// https://developer.garmin.com/connect-iq/api-docs/Toybox/ActivityMonitor/Info.html
// https://developer.garmin.com/connect-iq/api-docs/Toybox/System/Stats.html
class PrismelierData {
    // These are app policies, not Garmin refresh guarantees. Timestamp age is
    // checked even when expensive reads are throttled to once per clock minute.
    const WEATHER_STALE_SECONDS = 7200;
    const WEATHER_EXPIRE_SECONDS = 86400;
    const HEART_RATE_MAX_AGE_SECONDS = 120;
    // Body Battery history spacing is device dependent. Fifteen minutes is
    // this app's conservative expiry policy, not a live-reading guarantee.
    const BODY_BATTERY_MAX_AGE_SECONDS = 900;
    const SOLAR_CACHE_SECONDS = 3600;
    const SOLAR_RETRY_SECONDS = 300;

    var temperatureC as Lang.Numeric or Null = null;
    var weatherLabel as Lang.String = "NO WEATHER";
    var weatherKind as Lang.String = "unknown";
    var weatherStale as Lang.Boolean = false;
    var heartRate as Lang.Number or Null = null;
    var bodyBattery as Lang.Number or Null = null;
    var steps as Lang.Number or Null = null;
    var battery as Lang.Number or Null = null;
    var solarLabel as Lang.String = "SUN";
    var solarTime as Lang.String = "--:--";
    // Local calendar values. Null means no weekday should be highlighted.
    var weekdayIndex as Lang.Number or Null = null;
    var dateLabel as Lang.String = "--";
    var palette as Lang.Number = 0;

    private var _timeFormat as Lang.Number = 0;
    private var _temperatureUnits as Lang.Number = 0;
    private var _lastRefreshMinute as Lang.Number = -1;
    private var _heartRateAt as Lang.Number or Null = null;
    private var _bodyBatteryAt as Lang.Number or Null = null;
    private var _weatherPresent as Lang.Boolean = false;
    private var _weatherAt as Lang.Number or Null = null;
    private var _weatherTemperature as Lang.Numeric or Null = null;
    private var _weatherCondition as Lang.Number or Null = null;
    private var _location as Position.Location or Null = null;
    private var _locationAt as Lang.Number or Null = null;
    private var _solarEvents as Lang.Array = [];
    private var _solarKinds as Lang.Array = [];
    private var _solarDay as Lang.Number = -1;
    private var _solarLatitude as Lang.Numeric or Null = null;
    private var _solarLongitude as Lang.Numeric or Null = null;
    private var _solarBuiltAt as Lang.Number = -1;
    private var _solarRetryAfter as Lang.Number = 0;

    function initialize() {
        loadSettings();
        refresh(true);
    }

    // Call after an app-settings change; refresh(true) applies it immediately.
    function loadSettings() as Void {
        palette = readChoice("Palette", 3);
        _timeFormat = readChoice("TimeFormat", 2);
        _temperatureUnits = readChoice("TemperatureUnits", 2);
        _lastRefreshMinute = -1;
    }

    private function readChoice(key as Lang.String, maximum as Lang.Number)
            as Lang.Number {
        var value = Application.Properties.getValue(key);
        if (value instanceof Lang.Number && value >= 0 && value <= maximum) {
            return value;
        }
        return 0;
    }

    function is24Hour() as Lang.Boolean {
        if (_timeFormat == 1) { return false; }
        if (_timeFormat == 2) { return true; }
        return System.getDeviceSettings().is24Hour;
    }

    function isFahrenheit() as Lang.Boolean {
        if (_temperatureUnits == 1) { return false; }
        if (_temperatureUnits == 2) { return true; }
        return System.getDeviceSettings().temperatureUnits == System.UNIT_STATUTE;
    }

    // Pure formatter shared by the clock and solar events.
    function formatTime(hour as Lang.Number, minute as Lang.Number)
            as Lang.String {
        if (is24Hour()) {
            return hour.format("%02d") + ":" + minute.format("%02d");
        }
        var h = hour % 12;
        if (h == 0) { h = 12; }
        return h.format("%d") + ":" + minute.format("%02d");
    }

    function refresh(force as Lang.Boolean) as Void {
        var now = Time.now();
        var seconds = now.value();
        var minute = (seconds / 60).toNumber();
        // Always use current local calendar info, even inside a cached minute:
        // a timezone change can change the date without advancing UTC time.
        updateClockLabels(now);

        // Never keep an expired HR on screen until the next scheduled read.
        if (_heartRateAt == null || seconds < _heartRateAt ||
                seconds - _heartRateAt > HEART_RATE_MAX_AGE_SECONDS) {
            heartRate = null;
            _heartRateAt = null;
        }
        if (_bodyBatteryAt == null || seconds < _bodyBatteryAt ||
                seconds - _bodyBatteryAt > BODY_BATTERY_MAX_AGE_SECONDS) {
            bodyBattery = null;
            _bodyBatteryAt = null;
        }

        if (force || minute != _lastRefreshMinute) {
            _lastRefreshMinute = minute;
            readActivity();
            readHeartRate(seconds);
            readBodyBattery(seconds);
            readWeather(seconds);
            buildSolarEvents(now, seconds);
        }

        updateWeatherDisplay(seconds);
        updateSolarDisplay(seconds);
    }

    private function updateClockLabels(now as Time.Moment) as Void {
        // info() uses the watch's local timezone. FORMAT_SHORT yields numeric
        // weekday 1=Sunday..7=Saturday and month 1=January..12=December.
        // https://developer.garmin.com/connect-iq/api-docs/Toybox/Time/Gregorian/Info.html
        var info = Gregorian.info(now, Time.FORMAT_SHORT);
        var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        var weekday = info.day_of_week;
        var month = info.month;
        // Guard union-typed fields before arithmetic or array access. Invalid
        // calendar values must not preserve a stale date or select Sunday.
        weekdayIndex = null;
        dateLabel = "--";
        if (weekday instanceof Lang.Number && weekday >= 1 && weekday <= 7) {
            weekdayIndex = weekday - 1;
        }
        if (month instanceof Lang.Number && month >= 1 && month <= 12 &&
                info.day >= 1 && info.day <= 31) {
            dateLabel = months[month - 1] + " " + info.day.format("%d");
        }
    }

    private function readActivity() as Void {
        steps = null;
        battery = null;
        try {
            var info = ActivityMonitor.getInfo();
            if (info.steps != null && info.steps >= 0) {
                steps = info.steps;
            }
        } catch (e) {
            // Missing tracking data is unavailable, not an invented zero.
        }
        try {
            var value = System.getSystemStats().battery;
            if (value >= 0 && value <= 100) {
                battery = value.toNumber();
            }
        } catch (e) {
            // Other complications can still render if a system read fails.
        }
    }

    private function readHeartRate(nowSeconds as Lang.Number) as Void {
        heartRate = null;
        _heartRateAt = null;
        try {
            // A Duration is seconds; a Number here would mean sample count.
            var history = SensorHistory.getHeartRateHistory({
                :period => new Time.Duration(HEART_RATE_MAX_AGE_SECONDS),
                :order => SensorHistory.ORDER_NEWEST_FIRST
            });
            var sample = history.next();
            // This is a recent measurement, not an activated/live HR sensor.
            while (sample != null) {
                var age = nowSeconds - sample.when.value();
                if (age > HEART_RATE_MAX_AGE_SECONDS) { break; }
                if (age >= 0 && sample.data != null && sample.data > 0 &&
                        sample.data != ActivityMonitor.INVALID_HR_SAMPLE) {
                    heartRate = sample.data.toNumber();
                    _heartRateAt = sample.when.value();
                    break;
                }
                sample = history.next();
            }
        } catch (e) {
            // No fallback to a value with an unverifiable observation time.
        }
    }

    // Supported on FR265 in watch faces since API 3.3.0, using the existing
    // SensorHistory permission. This is the on-watch 0-100 wellness score,
    // not device charge, a percentage, or a score computed from other data.
    // https://developer.garmin.com/connect-iq/api-docs/Toybox/SensorHistory.html#getBodyBatteryHistory-instance_function
    private function readBodyBattery(nowSeconds as Lang.Number) as Void {
        bodyBattery = null;
        _bodyBatteryAt = null;
        if (!(SensorHistory has :getBodyBatteryHistory)) { return; }
        try {
            var history = SensorHistory.getBodyBatteryHistory({
                :period => new Time.Duration(BODY_BATTERY_MAX_AGE_SECONDS),
                :order => SensorHistory.ORDER_NEWEST_FIRST
            });
            var sample = history.next();
            while (sample != null) {
                var age = nowSeconds - sample.when.value();
                if (age > BODY_BATTERY_MAX_AGE_SECONDS) { break; }
                // Zero is a valid reported score; null is unavailable.
                if (age >= 0 && sample.data != null && sample.data >= 0 &&
                        sample.data <= 100) {
                    bodyBattery = sample.data.toNumber();
                    _bodyBatteryAt = sample.when.value();
                    break;
                }
                sample = history.next();
            }
        } catch (e) {
            // No synthetic score, stale fallback, sensor activation or upload.
        }
    }

    private function readWeather(nowSeconds as Lang.Number) as Void {
        try {
            var wx = Weather.getCurrentConditions();
            if (wx == null) {
                // A transient cache miss may retain our previous observation,
                // but its ORIGINAL observation time is never extended.
                return;
            }
            _weatherPresent = true;
            _weatherTemperature = wx.temperature;
            _weatherCondition = wx.condition;
            _weatherAt = wx.observationTime == null ? null : wx.observationTime.value();

            // Null may mean Positioning permission is absent; discard an old
            // location rather than silently continuing to use it in that case.
            _location = null;
            _locationAt = null;
            if (wx.observationLocationPosition != null && _weatherAt != null &&
                    nowSeconds >= _weatherAt &&
                    nowSeconds - _weatherAt < WEATHER_EXPIRE_SECONDS) {
                _location = wx.observationLocationPosition;
                _locationAt = _weatherAt;
            }
        } catch (e) {
            // Retained cache is aged below, including when disconnected.
        }
    }

    private function updateWeatherDisplay(nowSeconds as Lang.Number) as Void {
        temperatureC = null;
        weatherKind = "unknown";
        weatherLabel = "NO WEATHER";
        weatherStale = false;
        if (!_weatherPresent) { return; }

        // Without an observation timestamp, a 24-hour cutoff cannot be proven.
        if (_weatherAt == null) {
            weatherStale = true;
            weatherLabel = "AGE UNKNOWN";
            return;
        }
        var age = nowSeconds - _weatherAt;
        if (age < 0) {
            weatherStale = true;
            weatherLabel = "CHECK TIME";
            return;
        }
        if (age >= WEATHER_EXPIRE_SECONDS) {
            weatherStale = true;
            weatherLabel = "WX EXPIRED";
            return;
        }
        temperatureC = _weatherTemperature;
        setWeatherCondition(_weatherCondition);
        if (age >= WEATHER_STALE_SECONDS) {
            weatherStale = true;
            weatherLabel = "AGED " + (age / 3600).toNumber().format("%d") + "H";
        }
    }

    private function setWeatherCondition(condition as Lang.Number or Null) as Void {
        weatherKind = "unknown";
        weatherLabel = "UNKNOWN";
        if (condition == null) { return; }
        switch (condition) {
            case Weather.CONDITION_CLEAR:
            case Weather.CONDITION_FAIR:
            case Weather.CONDITION_MOSTLY_CLEAR:
                weatherKind = "sun"; weatherLabel = "CLEAR"; break;
            case Weather.CONDITION_PARTLY_CLOUDY:
            case Weather.CONDITION_PARTLY_CLEAR:
            case Weather.CONDITION_THIN_CLOUDS:
                weatherKind = "partly"; weatherLabel = "PARTLY CLOUDY"; break;
            case Weather.CONDITION_MOSTLY_CLOUDY:
            case Weather.CONDITION_CLOUDY:
                weatherKind = "cloud"; weatherLabel = "CLOUDY"; break;
            case Weather.CONDITION_WINDY:
                weatherKind = "wind"; weatherLabel = "WINDY"; break;
            case Weather.CONDITION_RAIN:
            case Weather.CONDITION_LIGHT_RAIN:
            case Weather.CONDITION_HEAVY_RAIN:
            case Weather.CONDITION_SCATTERED_SHOWERS:
            case Weather.CONDITION_LIGHT_SHOWERS:
            case Weather.CONDITION_SHOWERS:
            case Weather.CONDITION_HEAVY_SHOWERS:
            case Weather.CONDITION_DRIZZLE:
                weatherKind = "rain"; weatherLabel = "RAIN"; break;
            case Weather.CONDITION_CHANCE_OF_SHOWERS:
            case Weather.CONDITION_CLOUDY_CHANCE_OF_RAIN:
                weatherKind = "rain"; weatherLabel = "RAIN CHANCE"; break;
            case Weather.CONDITION_THUNDERSTORMS:
            case Weather.CONDITION_SCATTERED_THUNDERSTORMS:
            case Weather.CONDITION_TORNADO:
            case Weather.CONDITION_SQUALL:
            case Weather.CONDITION_HURRICANE:
            case Weather.CONDITION_TROPICAL_STORM:
                weatherKind = "storm"; weatherLabel = "STORM"; break;
            case Weather.CONDITION_CHANCE_OF_THUNDERSTORMS:
                weatherKind = "storm"; weatherLabel = "STORM RISK"; break;
            case Weather.CONDITION_SNOW:
            case Weather.CONDITION_LIGHT_SNOW:
            case Weather.CONDITION_HEAVY_SNOW:
            case Weather.CONDITION_FLURRIES:
                weatherKind = "snow"; weatherLabel = "SNOW"; break;
            case Weather.CONDITION_CHANCE_OF_SNOW:
            case Weather.CONDITION_CLOUDY_CHANCE_OF_SNOW:
                weatherKind = "snow"; weatherLabel = "SNOW CHANCE"; break;
            case Weather.CONDITION_WINTRY_MIX:
            case Weather.CONDITION_LIGHT_RAIN_SNOW:
            case Weather.CONDITION_HEAVY_RAIN_SNOW:
            case Weather.CONDITION_RAIN_SNOW:
            case Weather.CONDITION_CHANCE_OF_RAIN_SNOW:
            case Weather.CONDITION_CLOUDY_CHANCE_OF_RAIN_SNOW:
            case Weather.CONDITION_FREEZING_RAIN:
            case Weather.CONDITION_SLEET:
            case Weather.CONDITION_ICE_SNOW:
            case Weather.CONDITION_ICE:
            case Weather.CONDITION_HAIL:
                weatherKind = "snow"; weatherLabel = "ICY MIX"; break;
            case Weather.CONDITION_FOG:
            case Weather.CONDITION_MIST:
                weatherKind = "fog"; weatherLabel = "FOG"; break;
            case Weather.CONDITION_HAZY:
            case Weather.CONDITION_HAZE:
                weatherKind = "fog"; weatherLabel = "HAZE"; break;
            case Weather.CONDITION_SMOKE:
                weatherKind = "fog"; weatherLabel = "SMOKE"; break;
            case Weather.CONDITION_DUST:
            case Weather.CONDITION_SAND:
            case Weather.CONDITION_SANDSTORM:
            case Weather.CONDITION_VOLCANIC_ASH:
                weatherKind = "fog"; weatherLabel = "DUST / ASH"; break;
            case Weather.CONDITION_UNKNOWN_PRECIPITATION:
                weatherKind = "rain"; weatherLabel = "PRECIP"; break;
            default:
                // An unknown condition is never silently drawn as sunshine.
                break;
        }
    }

    private function buildSolarEvents(now as Time.Moment, nowSeconds as Lang.Number)
            as Void {
        if (_location == null || _locationAt == null ||
                nowSeconds < _locationAt ||
                nowSeconds - _locationAt >= WEATHER_EXPIRE_SECONDS) {
            _location = null;
            _locationAt = null;
            _solarEvents = [];
            _solarKinds = [];
            _solarBuiltAt = -1;
            return;
        }
        try {
            var day = Time.today().value();
            var coordinates = _location.toDegrees();
            // Observation timestamp changes alone do not change solar events.
            // Exact coordinates and local midnight also cover travel and DST.
            if (_solarBuiltAt >= 0 && nowSeconds >= _solarBuiltAt &&
                    nowSeconds < _solarRetryAfter && day == _solarDay &&
                    coordinates[0] == _solarLatitude &&
                    coordinates[1] == _solarLongitude) {
                return;
            }
            _solarDay = day;
            _solarLatitude = coordinates[0];
            _solarLongitude = coordinates[1];
            _solarBuiltAt = nowSeconds;
            _solarRetryAfter = nowSeconds + SOLAR_RETRY_SECONDS;
            _solarEvents = [];
            _solarKinds = [];
            // Noon anchors avoid a midnight/DST boundary when stepping a day.
            // today() is local midnight; both arguments remain UTC Moments.
            var today = Time.today().add(new Time.Duration(43200));
            var tomorrow = today.add(new Time.Duration(86400));
            addSolarEvent(Weather.getSunrise(_location, today), "SUNRISE");
            addSolarEvent(Weather.getSunset(_location, today), "SUNSET");
            addSolarEvent(Weather.getSunrise(_location, tomorrow), "SUNRISE");
            addSolarEvent(Weather.getSunset(_location, tomorrow), "SUNSET");
            // Null/polar events are valid results too; don't recalculate them
            // every minute. Failures retry sooner, without a busy loop.
            _solarRetryAfter = nowSeconds + SOLAR_CACHE_SECONDS;
        } catch (e) {
            // Missing permission or polar/no-event results must not crash time.
            _solarEvents = [];
            _solarKinds = [];
            _solarBuiltAt = nowSeconds;
            _solarRetryAfter = nowSeconds + SOLAR_RETRY_SECONDS;
        }
    }

    private function addSolarEvent(event as Time.Moment or Null, label as Lang.String)
            as Void {
        if (event != null) {
            _solarEvents.add(event);
            _solarKinds.add(label);
        }
    }

    private function updateSolarDisplay(nowSeconds as Lang.Number) as Void {
        solarLabel = "SUN";
        solarTime = "--:--";
        if (_locationAt == null || nowSeconds < _locationAt ||
                nowSeconds - _locationAt >= WEATHER_EXPIRE_SECONDS) {
            return;
        }
        var best = null as Time.Moment or Null;
        for (var i = 0; i < _solarEvents.size(); i += 1) {
            var candidate = _solarEvents[i] as Time.Moment;
            if (candidate.value() > nowSeconds &&
                    (best == null || candidate.value() < best.value())) {
                best = candidate;
                solarLabel = _solarKinds[i] as Lang.String;
            }
        }
        if (best == null) { return; }
        // Asterisk = weather-derived location is at least two hours old.
        if (nowSeconds - _locationAt >= WEATHER_STALE_SECONDS) {
            solarLabel += "*";
        }
        var info = Gregorian.info(best, Time.FORMAT_SHORT);
        solarTime = formatTime(info.hour, info.min);
        if (!is24Hour()) {
            solarTime += info.hour < 12 ? " AM" : " PM";
        }
    }
}
