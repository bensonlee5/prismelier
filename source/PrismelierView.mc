using Toybox.Application;
using Toybox.Graphics;
using Toybox.Math;
using Toybox.System;
using Toybox.Time;
using Toybox.WatchUi;

// 416px FR265: one static Foundry material bitmap plus live vector overlays.
// Digital time, Sunday-first calendar rim and live speedometer temperature band.
class PrismelierView extends WatchUi.WatchFace {
    var data;
    var sleeping = false;
    var timeFont;
    var valueFont;
    var smallFont;
    var labelFont;
    var ambientFont;
    var gaugeFont;
    var gaugeScaleFont;
    var ink = 0xF2EDD8;
    var copper = 0xD98B52;
    var green = 0xC7FF70;
    var pink = 0xF474E8;
    var cyan = 0x6BE4DE;
    var muted = 0x786D82;
    var theme = 0;
    var background = null;
    var laidOut = false;
    // Two flat arrays avoid per-frame trigonometry and 144 temporary point
    // arrays for the 72-segment temperature band. No full-screen buffer.
    var bandX = [];
    var bandY = [];
    // Theme colors resolved once per theme; PrismelierPalette.color() is a
    // 67-case switch and paint() runs hundreds of times per awake redraw.
    var colors = {};

    function initialize() {
        WatchFace.initialize();
        data = new PrismelierData();
        theme = data.palette;
        for (var j = 0; j <= 72; j += 1) {
            var p = point(133, 263, 59, 135.0 + 270.0 * j / 72);
            bandX.add(p[0]);
            bandY.add(p[1]);
        }
    }

    function onLayout(dc) {
        timeFont = WatchUi.loadResource(Rez.Fonts.Time);
        valueFont = WatchUi.loadResource(Rez.Fonts.Value);
        smallFont = WatchUi.loadResource(Rez.Fonts.Small);
        labelFont = WatchUi.loadResource(Rez.Fonts.Label);
        ambientFont = WatchUi.loadResource(Rez.Fonts.Ambient);
        gaugeFont = WatchUi.loadResource(Rez.Fonts.Gauge);
        gaugeScaleFont = WatchUi.loadResource(Rez.Fonts.GaugeScale);
        laidOut = true;
        refreshTexture();
    }

    function reloadSettings() {
        data.loadSettings();
        theme = data.palette;
        colors = {};
        if (laidOut) { refreshTexture(); }
        data.refresh(true);
    }

    function refreshTexture() {
        if (theme != 1) {
            background = null;
        } else if (background == null) {
            try {
                background = WatchUi.loadResource(Rez.Drawables.FoundryBackground);
            } catch (e) {
                background = null; // Recoverable resource failure: use vector art.
            }
        }
    }

    function usesTexture() {
        return theme == 1 && background != null;
    }

    function onShow() {
        if (!sleeping) { data.startBodyBatteryUpdates(); }
    }

    function onHide() {
        data.stopBodyBatteryUpdates();
    }

    function onEnterSleep() {
        sleeping = true;
        data.stopBodyBatteryUpdates();
        WatchUi.requestUpdate();
    }

    function onExitSleep() {
        sleeping = false;
        data.startBodyBatteryUpdates();
        // onUpdate performs the ordinary minute-cached refresh. Repeated
        // gestures must not force history/weather reads inside one minute.
        WatchUi.requestUpdate();
    }

    function paint(dc, foreground, background) {
        var c = colors[foreground];
        if (c == null) {
            c = PrismelierPalette.color(foreground, theme);
            colors[foreground] = c;
        }
        dc.setColor(c, background);
    }

    function text(dc, x, y, font, s, color) {
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, y, font, s, Graphics.TEXT_JUSTIFY_CENTER);
    }

    function stroke(dc, x1, y1, x2, y2, color, width) {
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(width);
        dc.drawLine(x1, y1, x2, y2);
        dc.setPenWidth(1);
    }

    function point(cx, cy, r, degrees) {
        var a = degrees * Math.PI / 180.0;
        return [cx + Math.cos(a) * r, cy + Math.sin(a) * r];
    }

    function radial(dc, cx, cy, inner, outer, angle, color, width) {
        var a = point(cx, cy, inner, angle);
        var b = point(cx, cy, outer, angle);
        stroke(dc, a[0], a[1], b[0], b[1], color, width);
    }

    function clamp(value, low, high) {
        if (value < low) { return low; }
        if (value > high) { return high; }
        return value;
    }

    function onUpdate(dc) {
        dc.clearClip();
        dc.setAntiAlias(true);
        var clock = System.getClockTime();
        var time = data.formatTime(clock.hour, clock.min);
        if (sleeping) {
            paint(dc, Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
            dc.clear();
            // Refresh only local calendar labels; no weather or sensor reads.
            data.refreshCalendar();
            // Move both lines together between non-overlapping safe bands.
            var slot = (Time.now().value() / 60).toNumber() % 3;
            var y = 60 + slot * 100;
            var weekdays = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY",
                "THURSDAY", "FRIDAY", "SATURDAY"];
            var weekday = data.weekdayIndex == null ? "--" : weekdays[data.weekdayIndex];
            text(dc, 208, y, ambientFont, time, 0xA09785);
            text(dc, 208, y + 85, labelFont, weekday + "  " + data.glanceDateLabel, 0x84644C);
            return;
        }
        data.refresh(false);
        // Firmware may clear/replace the display before every onUpdate.
        // Always produce a complete frame; only sensor data is cached.
        paint(dc, Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        if (usesTexture()) {
            // Retain only the resource reference. Do not pin with .get() or
            // copy the image into a second full-screen BufferedBitmap.
            try {
                dc.drawBitmap(0, 0, background);
            } catch (e) {
                background = null;
                paint(dc, Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
                dc.clear();
                drawArchitecture(dc);
                drawRobotics(dc);
                drawMachine(dc);
            }
        } else {
            drawArchitecture(dc);
            drawRobotics(dc);
            drawMachine(dc);
        }
        drawCalendar(dc);
        drawBattery(dc);
        drawBodyBattery(dc);
        if (data.is24Hour()) {
            text(dc, 208, 77, timeFont, time, green);
        } else {
            // Suffix sits inside the visor's lower-right corner, beside the digits.
            text(dc, 192, 77, timeFont, time, green);
            text(dc, 324, 148, labelFont, clock.hour < 12 ? "AM" : "PM", ink);
        }
        drawTemperature(dc);
        drawWeatherRails(dc);
        drawVitals(dc);
    }

    function drawHeartRate(dc) {
        text(dc, 149, 339, valueFont, data.heartRate == null ? "--" : data.heartRate.format("%d"), ink);
    }

    function screw(dc, x, y, color) {
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x, y, 3);
        stroke(dc, x - 2, y + 1, x + 2, y - 1, 0x241620, 1);
    }

    function gear(dc, x, y, r, color) {
        for (var i = 0; i < 12; i += 1) {
            radial(dc, x, y, r - 2, r + 3, i * 30, color, 4);
        }
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(3);
        dc.drawCircle(x, y, r - 3);
        dc.setPenWidth(1);
        dc.drawCircle(x, y, r - 8);
        for (var a = 0; a < 3; a += 1) {
            radial(dc, x, y, 4, r - 8, a * 120 + 25, color, 3);
        }
        paint(dc, 0xD6D9BF, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x, y, 4);
        screw(dc, x, y, copper);
    }

    function trace(dc, points, color, width) {
        for (var i = 1; i < points.size(); i += 1) {
            stroke(dc, points[i - 1][0], points[i - 1][1], points[i][0], points[i][1], color, width);
        }
    }

    function junction(dc, x, y, color) {
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(x, y, 3);
        dc.fillCircle(x, y, 1);
    }

    function drawArchitecture(dc) {
        // The seven live weekday pockets are calendar positions, not clock indices.
        paint(dc, 0x071214, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(208, 208, 199);
        paint(dc, 0x344741, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(208, 208, 198);
        paint(dc, 0x102226, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(102, 50, 106, 30, 7);
        dc.fillRoundedRectangle(219, 50, 91, 30, 7);
        // Black ceramic digital-time visor, polished timber/copper surrounds.
        paint(dc, 0x452744, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(62, 84, 292, 94, 14);
        for (var grain = 0; grain < 5; grain += 1) {
            stroke(dc, 70, 88 + grain * 19, 346, 90 + grain * 19, 0x85506D, 1);
        }
        paint(dc, 0x080F13, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(69, 90, 278, 81, 9);
        paint(dc, copper, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(62, 84, 292, 94, 14);
        stroke(dc, 80, 85, 336, 85, 0xF2BF8C, 1);
        paint(dc, 0x102226, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(160, 177, 96, 28, 5);
        paint(dc, 0x3C6260, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(160, 177, 96, 28, 5);
        // Companion weather bay and a light ceramic solar insert.
        paint(dc, 0x122325, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(218, 209, 137, 115, 13);
        paint(dc, copper, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(218, 209, 137, 115, 13);
        paint(dc, 0xD6D9BF, Graphics.COLOR_TRANSPARENT);
        dc.fillPolygon([[229, 273], [343, 273], [349, 280], [344, 310], [227, 310], [223, 303]]);
        stroke(dc, 231, 275, 339, 275, 0xF5F5DB, 1);

    }

    function drawRobotics(dc) {
        for (var side = 0; side < 2; side += 1) {
            var x = side == 0 ? 31 : 373;
            paint(dc, 0x080F13, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x, 162, 12, 44, 3);
            for (var pin = 0; pin < 7; pin += 1) {
                stroke(dc, x + 3, 166 + pin * 5, x + 9, 166 + pin * 5, copper, 2);
            }
        }
        for (var ribbon = 0; ribbon < 4; ribbon += 1) {
            trace(dc, [[82 + ribbon * 5, 73], [69 + ribbon * 5, 75], [49 + ribbon * 5, 94], [49 + ribbon * 5, 124]], 0x8B6544, 1);
            trace(dc, [[334 - ribbon * 5, 73], [347 - ribbon * 5, 75], [367 - ribbon * 5, 94], [367 - ribbon * 5, 124]], 0x335657, 1);
        }
        trace(dc, [[27, 222], [31, 291], [66, 330], [78, 330]], 0x4F958B, 2);
        trace(dc, [[386, 225], [382, 300], [347, 333], [328, 333]], 0x8B6544, 2);
        gear(dc, 365, 239, 11, cyan);
        screw(dc, 219, 333, copper);
        screw(dc, 351, 322, copper);
        paint(dc, 0x080F13, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(181, 383, 54, 15, 3);
        paint(dc, 0x3C6260, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(181, 383, 54, 15, 3);
        for (var p = 0; p < 6; p += 1) {
            stroke(dc, 185 + p * 9, 380, 185 + p * 9, 383, copper, 2);
        }
    }

    function drawMachine(dc) {
        // A high-quality wood bezel carries the temperature instrument only.
        paint(dc, 0x452744, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(133, 263, 74);
        paint(dc, 0x85506D, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(133, 263, 71);
        paint(dc, copper, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawCircle(133, 263, 67);
        dc.setPenWidth(1);
        paint(dc, 0x091B23, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(133, 263, 64);
        screw(dc, 83, 209, copper);
        screw(dc, 184, 209, copper);
        screw(dc, 83, 318, copper);
        screw(dc, 184, 318, copper);
        paint(dc, 0x080F13, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(83, 342, 254, 38, 7);
        paint(dc, 0x6B4839, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(83, 342, 254, 38, 7);
        for (var side = 0; side < 2; side += 1) {
            var x = side == 0 ? 30 : 365;
            paint(dc, 0x080F13, Graphics.COLOR_TRANSPARENT);
            dc.fillRoundedRectangle(x, 220, 24, 86, 5);
            paint(dc, copper, Graphics.COLOR_TRANSPARENT);
            dc.drawRoundedRectangle(x, 220, 24, 86, 5);
        }
    }

    function drawCalendar(dc) {
        var initials = ["S", "M", "T", "W", "T", "F", "S"];
        for (var i = 0; i < 7; i += 1) {
            var pos = point(208, 208, 188, 210 + i * 20);
            var current = data.weekdayIndex != null && data.weekdayIndex == i;
            // Today is an inverted copper plate, distinct from the other T/S.
            paint(dc, current ? copper : 0x071214, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(pos[0], pos[1], 12);
            text(dc, pos[0], pos[1] - 12, smallFont, initials[i], current ? 0x091B23 : 0x74ACA0);
        }
        text(dc, 208, 176, smallFont, data.dateLabel, ink);
    }

    function drawBattery(dc) {
        var dx = -5;
        // Icon center matches the Small font's visible digits (y=52..67).
        var dy = 3;
        paint(dc, cyan, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawRoundedRectangle(121 + dx, 51 + dy, 17, 10, 2);
        dc.setPenWidth(1);
        stroke(dc, 139 + dx, 54 + dy, 139 + dx, 58 + dy, cyan, 2);
        if (data.battery != null) {
            stroke(dc, 125 + dx, 56 + dy, 125 + dx + (9 * clamp(data.battery, 0, 100) / 100).toNumber(), 56 + dy, cyan, 2);
        }
        var reading = data.battery == null ? "--%" : data.battery.format("%d") + "%";
        text(dc, 174 + dx, 48, smallFont, reading, data.battery != null && data.battery <= 15 ? pink : cyan);
    }

    function drawBodyBattery(dc) {
        // Original monoline person + energy bolt; a score, never a percentage.
        // Compact person stays within the top pocket, centered on the score.
        var y = 60;
        paint(dc, pink, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawCircle(235, y - 7, 3);
        dc.setPenWidth(1);
        stroke(dc, 235, y - 1, 235, y + 3, pink, 2);
        stroke(dc, 230, y, 240, y, pink, 2);
        stroke(dc, 235, y + 3, 231, y + 7, pink, 2);
        stroke(dc, 235, y + 3, 239, y + 7, pink, 2);
        trace(dc, [[246, y - 7], [242, y], [247, y], [243, y + 7]], copper, 1);
        text(dc, 280, 48, smallFont, data.bodyBattery == null ? "--" : data.bodyBattery.format("%d"), ink);
    }

    function drawWeatherRails(dc) {
        // Selected A: matched left RH and right daily precipitation rails.
        // Keep labels inside the narrow dark wells, clear of the copper frame.
        text(dc, 42, 225, gaugeFont, "RH", cyan);
        // Miniature rain cloud; intentionally distinct from the current icon.
        trace(dc, [[370, 231], [370, 229], [372, 228], [374, 228],
            [375, 225], [378, 225], [380, 228], [382, 229], [382, 232],
            [370, 232]], cyan, 1);
        stroke(dc, 373, 234, 372, 236, cyan, 1);
        stroke(dc, 377, 234, 376, 236, cyan, 1);
        stroke(dc, 381, 234, 380, 236, cyan, 1);
        drawWeatherRail(dc, 42, data.humidity, cyan);
        drawWeatherRail(dc, 376, data.precipitationChance, copper);
    }

    function drawWeatherRail(dc, x, value, fillColor) {
        var color = data.weatherStale ? copper : fillColor;
        paint(dc, 0x224142, Graphics.COLOR_TRANSPARENT);
        dc.fillRectangle(x - 2.5, 244, 5, 34);
        if (value != null) {
            var height = 34.0 * clamp(value, 0, 100) / 100.0;
            if (height > 0) {
                paint(dc, color, Graphics.COLOR_TRANSPARENT);
                dc.fillRectangle(x - 2.5, 278 - height, 5, height);
            }
            stroke(dc, x - 4, 278 - height, x + 4, 278 - height, ink, 1);
        } else {
            // Missing is a crossed track and --%, never a fabricated zero.
            stroke(dc, x - 3, 257, x + 3, 265, muted, 1);
            stroke(dc, x - 3, 265, x + 3, 257, muted, 1);
        }
        // A separate unit line keeps every 0..100 reading within the 16px well.
        text(dc, x, 286, gaugeScaleFont, value == null ? "--" : value.format("%d"), color);
        text(dc, x, 296, gaugeScaleFont, "%", color);
    }

    function drawTemperature(dc) {
        var fahrenheit = data.isFahrenheit();
        var low = fahrenheit ? 0 : -20;
        var high = fahrenheit ? 120 : 40;
        var val = data.temperatureC;
        if (val != null && fahrenheit) { val = val * 9.0 / 5.0 + 32.0; }
        var f = val == null ? 0.0 : clamp((val - low).toFloat() / (high - low), 0.0, 1.0);
        // Thin full-scale track; the thick overlay represents today's range.
        // The needle alone represents the current temperature.
        for (var j = 0; j < 72; j += 1) {
            stroke(dc, bandX[j], bandY[j], bandX[j + 1], bandY[j + 1], 0x224142, 3);
        }
        drawForecastRange(dc, fahrenheit, low, high);
        for (var tick = 0; tick <= 12; tick += 1) {
            radial(dc, 133, 263, tick % 4 == 0 ? 48 : 51, 54,
                135.0 + tick * 22.5, 0x74ACA0, 1);
        }
        text(dc, 133, 280, labelFont, fahrenheit ? "°F" : "°C", 0x74ACA0);
        var labels = fahrenheit ? ["0", "40", "80", "120"] : ["-20", "0", "20", "40"];
        for (var label = 0; label < 4; label += 1) {
            var lp = point(133, 263, 42, 135 + label * 90);
            text(dc, lp[0], lp[1] - 9, labelFont, labels[label], ink);
        }
        if (val != null) {
            var needleAngle = 135.0 + 270.0 * f;
            radial(dc, 133, 263, -5, 30, needleAngle, data.weatherStale ? copper : 0xFFC9FA, 3);
            radial(dc, 133, 263, 56, 64, needleAngle, ink, 2);
            if (val < low || val > high) {
                // Outward chevron explicitly signals a clamped scale endpoint.
                var tip = point(133, 263, 65, needleAngle);
                var left = point(133, 263, 59, needleAngle - 4);
                var right = point(133, 263, 59, needleAngle + 4);
                stroke(dc, left[0], left[1], tip[0], tip[1], ink, 2);
                stroke(dc, right[0], right[1], tip[0], tip[1], ink, 2);
            }
            paint(dc, copper, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(133, 263, 4);
            paint(dc, 0x091B23, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(133, 263, 2);
        }
        drawWeather(dc, 284, 228, data.weatherKind);
        text(dc, 286, 242, labelFont, data.weatherLabel, data.weatherStale ? copper : ink);
        if (data.weatherStale) {
            paint(dc, copper, Graphics.COLOR_TRANSPARENT);
            dc.drawCircle(312, 220, 3);
            stroke(dc, 310, 222, 314, 218, copper, 1);
        }
        drawSolar(dc);
    }

    function drawForecastRange(dc, fahrenheit, dialLow, dialHigh) {
        var low = data.forecastLowC;
        var high = data.forecastHighC;
        if (low == null || high == null || !(low <= high)) { return; }
        if (fahrenheit) {
            low = low * 9.0 / 5.0 + 32.0;
            high = high * 9.0 / 5.0 + 32.0;
        }
        var start = clamp((low - dialLow).toFloat() / (dialHigh - dialLow), 0.0, 1.0) * 72;
        var end = clamp((high - dialLow).toFloat() / (dialHigh - dialLow), 0.0, 1.0) * 72;
        // Overlay a thicker copper bar on the existing scale. Interpolate the
        // two boundary chords so short ranges do not expand to whole segments.
        // Reuse cached geometry; no new per-segment trigonometry or buffers.
        for (var j = 0; j < 72; j += 1) {
            var from = clamp(start - j, 0.0, 1.0);
            var to = clamp(end - j, 0.0, 1.0);
            if (to <= from) { continue; }
            var dx = bandX[j + 1] - bandX[j];
            var dy = bandY[j + 1] - bandY[j];
            stroke(dc, bandX[j] + dx * from, bandY[j] + dy * from,
                bandX[j] + dx * to, bandY[j] + dy * to, copper, 9);
        }
        // Equal in-scale bounds are a single tick, never an invented interval.
        if (low == high && low >= dialLow && high <= dialHigh) {
            radial(dc, 133, 263, 55, 63, 135.0 + 270.0 * start / 72, copper, 3);
        }
        // Entirely out-of-scale ranges show only the relevant overflow mark.
        if (low < dialLow) { drawForecastOverflow(dc, 135); }
        if (high > dialHigh) { drawForecastOverflow(dc, 405); }
    }

    function drawForecastOverflow(dc, angle) {
        var tip = point(133, 263, 70, angle);
        var left = point(133, 263, 65, angle - 4);
        var right = point(133, 263, 65, angle + 4);
        stroke(dc, left[0], left[1], tip[0], tip[1], copper, 2);
        stroke(dc, right[0], right[1], tip[0], tip[1], copper, 2);
    }

    function drawVitals(dc) {
        var dy = 22;
        // Heart outline and two footprint outlines share a 2px monoline weight.
        trace(dc, [[104, 341 + dy], [95, 332 + dy], [95, 327 + dy],
            [98, 324 + dy], [102, 324 + dy], [104, 327 + dy], [106, 324 + dy],
            [110, 324 + dy], [113, 327 + dy], [113, 332 + dy], [104, 341 + dy]], pink, 2);
        drawHeartRate(dc);
        paint(dc, cyan, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawEllipse(220, 350, 6, 9);
        dc.drawEllipse(229, 356, 6, 9);
        dc.drawCircle(223, 346, 2);
        dc.drawCircle(232, 352, 2);
        dc.setPenWidth(1);
        // Smaller fonts need lower origins to keep their visible ink centered.
        var stepY = data.steps != null && data.steps >= 1000000 ? 346 :
            (data.steps != null && data.steps >= 10000 ? 342 : 339);
        text(dc, 284, stepY, data.steps != null && data.steps >= 1000000 ? labelFont : (data.steps != null && data.steps >= 10000 ? smallFont : valueFont), data.steps == null ? "--" : formatSteps(data.steps), ink);
    }

    function formatSteps(n) {
        if (n < 1000) { return n.format("%d"); }
        return (n / 1000).toNumber().format("%d") + "," + (n % 1000).format("%03d");
    }

    function drawWeather(dc, x, y, kind) {
        var color = data.weatherStale ? copper : cyan;
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        if (kind.equals("sun")) {
            if (data.solarLabel.find("RISE") != null) {
                trace(dc, [[x - 4, y - 11], [x - 10, y - 7], [x - 12, y],
                    [x - 9, y + 8], [x - 2, y + 11], [x + 6, y + 8], [x + 10, y + 3],
                    [x + 3, y + 4], [x - 3, y], [x - 5, y - 6], [x - 4, y - 11]], color, 2);
            } else {
                dc.drawCircle(x, y, 7);
                for (var r = 0; r < 8; r += 1) { radial(dc, x, y, 11, 14, r * 45, color, 2); }
            }
        } else if (kind.equals("wind")) {
            trace(dc, [[x - 14, y - 5], [x + 7, y - 5], [x + 10, y - 8], [x + 8, y - 11], [x + 5, y - 11]], color, 2);
            trace(dc, [[x - 10, y + 1], [x + 14, y + 1], [x + 16, y + 4], [x + 13, y + 7]], color, 2);
            stroke(dc, x - 14, y + 7, x + 5, y + 7, color, 2);
        } else if (kind.equals("fog")) {
            stroke(dc, x - 14, y - 5, x + 14, y - 5, color, 2);
            stroke(dc, x - 10, y + 1, x + 10, y + 1, color, 2);
            stroke(dc, x - 14, y + 7, x + 14, y + 7, color, 2);
        } else {
            if (kind.equals("partly")) {
                trace(dc, [[x + 3, y - 13], [x + 7, y - 16], [x + 12, y - 15],
                    [x + 15, y - 11], [x + 14, y - 6]], copper, 2);
                radial(dc, x + 8, y - 10, 8, 10, 270, copper, 2);
                radial(dc, x + 8, y - 10, 8, 10, 315, copper, 2);
                radial(dc, x + 8, y - 10, 8, 10, 0, copper, 2);
            }
            trace(dc, [[x - 12, y + 7], [x - 15, y + 4], [x - 15, y], [x - 12, y - 4],
                [x - 7, y - 5], [x - 5, y - 10], [x, y - 13], [x + 6, y - 11],
                [x + 9, y - 6], [x + 10, y - 2], [x + 14, y], [x + 16, y + 4],
                [x + 13, y + 7], [x - 12, y + 7]], color, 2);
            if (kind.equals("rain")) {
                stroke(dc, x - 7, y + 9, x - 10, y + 13, color, 2);
                stroke(dc, x + 2, y + 9, x - 1, y + 13, color, 2);
                stroke(dc, x + 11, y + 9, x + 8, y + 13, color, 2);
            } else if (kind.equals("storm")) {
                trace(dc, [[x + 3, y + 8], [x - 2, y + 12], [x + 5, y + 12], [x, y + 14]], color, 2);
            } else if (kind.equals("snow")) {
                stroke(dc, x, y + 9, x, y + 14, color, 2);
                stroke(dc, x - 4, y + 9, x + 4, y + 14, color, 2);
                stroke(dc, x - 4, y + 14, x + 4, y + 9, color, 2);
            }
        }
        dc.setPenWidth(1);
        if (kind.equals("unknown") || data.weatherStale) {
            stroke(dc, x - 17, y + 16, x + 17, y - 17, copper, 2);
        }
    }

    function drawSolar(dc) {
        var x = 247;
        var up = data.solarLabel.find("RISE") != null;
        // Rise and set have different icon extents; both center at y=294.
        var y = up ? 303 : 296;
        var color = data.solarTime.equals("--:--") ? 0x777F70 : (up ? 0x27645D : 0xA04D30);
        var sunY = up ? y - 4 : y;
        // Open upper semicircle preserves the material texture underneath.
        for (var a = 180; a < 360; a += 15) {
            var p1 = point(x, sunY, 8, a);
            var p2 = point(x, sunY, 8, a + 15);
            stroke(dc, p1[0], p1[1], p2[0], p2[1], color, 2);
        }
        stroke(dc, x - 14, y, x + 12, y, color, 2);
        radial(dc, x, sunY, 11, 14, 220, color, 2);
        radial(dc, x, sunY, 11, 14, 270, color, 2);
        radial(dc, x, sunY, 11, 14, 320, color, 2);
        if (!data.solarTime.equals("--:--")) {
            var tipY = up ? y - 12 : y + 10;
            var baseY = up ? tipY + 5 : tipY - 5;
            stroke(dc, x + 16, up ? y - 12 : y + 1, x + 16, up ? y - 3 : y + 10, color, 2);
            stroke(dc, x + 12, baseY, x + 16, tipY, color, 2);
            stroke(dc, x + 20, baseY, x + 16, tipY, color, 2);
        }
        // "5:03 PM" needs the Label font to fit the plate; 24-hour and "--:--" use Small.
        if (data.solarTime.length() > 5) {
            text(dc, 307, 285, labelFont, data.solarTime, 0x183B3B);
        } else {
            text(dc, 307, 282, smallFont, data.solarTime, 0x183B3B);
        }
        if (data.solarLabel.find("*") != null) {
            paint(dc, copper, Graphics.COLOR_TRANSPARENT);
            dc.drawCircle(340, 307, 3);
        }
    }
}
