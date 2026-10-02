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
            var p = point(137, 267, 59, 135.0 + 270.0 * j / 72);
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

    function onEnterSleep() {
        sleeping = true;
        WatchUi.requestUpdate();
    }

    function onExitSleep() {
        sleeping = false;
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
        paint(dc, Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        dc.setAntiAlias(true);
        var clock = System.getClockTime();
        var time = data.formatTime(clock.hour, clock.min);
        if (sleeping) {
            // Disjoint bands, not a cosmetic 1px shift: old AMOLED rules safe
            // in the asset model. Real firmware validation is still required.
            var slot = (Time.now().value() / 60).toNumber() % 3;
            var y = 92 + slot * 86;
            text(dc, 208, y, ambientFont, time, 0x606775);
            return;
        }
        data.refresh(false);
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
        drawVitals(dc);
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
        paint(dc, 0x080F13, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(83, 342, 254, 38, 7);
        paint(dc, 0x6B4839, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(83, 342, 254, 38, 7);
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
        dc.fillCircle(137, 267, 74);
        paint(dc, 0x85506D, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(137, 267, 71);
        paint(dc, copper, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawCircle(137, 267, 67);
        dc.setPenWidth(1);
        paint(dc, 0x091B23, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(137, 267, 64);
        screw(dc, 87, 213, copper);
        screw(dc, 188, 213, copper);
        screw(dc, 87, 322, copper);
        screw(dc, 188, 322, copper);
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
        text(dc, 208, 175, smallFont, data.dateLabel, ink);
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
        var dy = 6;
        paint(dc, pink, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawCircle(235, 47 + dy, 3);
        dc.setPenWidth(1);
        stroke(dc, 235, 53 + dy, 235, 60 + dy, pink, 2);
        stroke(dc, 230, 55 + dy, 240, 55 + dy, pink, 2);
        stroke(dc, 235, 60 + dy, 231, 66 + dy, pink, 2);
        stroke(dc, 235, 60 + dy, 239, 66 + dy, pink, 2);
        trace(dc, [[246, 48 + dy], [242, 55 + dy], [247, 55 + dy], [243, 62 + dy]], copper, 1);
        text(dc, 280, 42 + dy, smallFont, data.bodyBattery == null ? "--" : data.bodyBattery.format("%d"), ink);
    }

    function drawTemperature(dc) {
        var fahrenheit = data.isFahrenheit();
        var low = fahrenheit ? 0 : -20;
        var high = fahrenheit ? 120 : 40;
        var val = data.temperatureC;
        if (val != null && fahrenheit) { val = val * 9.0 / 5.0 + 32.0; }
        var f = val == null ? 0.0 : clamp((val - low).toFloat() / (high - low), 0.0, 1.0);
        // Car-instrument sweep: 270 degrees, lower-left to lower-right.
        // A continuous graduated band encodes the value; needle is temperature,
        // never time. Color shifts from cool cyan through ivory to warm copper.
        for (var j = 0; j < 72; j += 1) {
            var active = val != null && (j + 0.5) / 72.0 <= f;
            var bandColor = 0x224142;
            if (active) {
                bandColor = data.weatherStale ? 0x80665C :
                    (j < 24 ? 0x6BE4DE : (j < 48 ? 0xD6D9BF : 0xD98B52));
            }
            stroke(dc, bandX[j], bandY[j], bandX[j + 1], bandY[j + 1], bandColor, 7);
        }
        for (var tick = 0; tick <= 12; tick += 1) {
            radial(dc, 137, 267, tick % 4 == 0 ? 48 : 51, 54,
                135.0 + tick * 22.5, 0x74ACA0, 1);
        }
        text(dc, 137, 284, labelFont, fahrenheit ? "°F" : "°C", 0x74ACA0);
        var labels = fahrenheit ? ["0", "40", "80", "120"] : ["-20", "0", "20", "40"];
        for (var label = 0; label < 4; label += 1) {
            var lp = point(137, 267, 42, 135 + label * 90);
            text(dc, lp[0], lp[1] - 9, labelFont, labels[label], ink);
        }
        if (val != null) {
            var needleAngle = 135.0 + 270.0 * f;
            radial(dc, 137, 267, -5, 30, needleAngle, data.weatherStale ? copper : 0xFFC9FA, 3);
            radial(dc, 137, 267, 56, 63, needleAngle, ink, 2);
            if (val < low || val > high) {
                // Outward chevron explicitly signals a clamped scale endpoint.
                var tip = point(137, 267, 65, needleAngle);
                var left = point(137, 267, 59, needleAngle - 4);
                var right = point(137, 267, 59, needleAngle + 4);
                stroke(dc, left[0], left[1], tip[0], tip[1], ink, 2);
                stroke(dc, right[0], right[1], tip[0], tip[1], ink, 2);
            }
            paint(dc, copper, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(137, 267, 4);
            paint(dc, 0x091B23, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(137, 267, 2);
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

    function drawVitals(dc) {
        var dy = 24;
        // Heart outline and two footprint outlines share a 2px monoline weight.
        trace(dc, [[101, 341 + dy], [92, 332 + dy], [92, 327 + dy],
            [95, 324 + dy], [99, 324 + dy], [101, 327 + dy], [103, 324 + dy],
            [107, 324 + dy], [110, 327 + dy], [110, 332 + dy], [101, 341 + dy]], pink, 2);
        text(dc, 149, 338, valueFont, data.heartRate == null ? "--" : data.heartRate.format("%d"), ink);
        paint(dc, cyan, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        dc.drawEllipse(220, 350, 6, 9);
        dc.drawEllipse(229, 356, 6, 9);
        dc.drawCircle(223, 346, 2);
        dc.drawCircle(232, 352, 2);
        dc.setPenWidth(1);
        text(dc, 284, 338, data.steps != null && data.steps >= 1000000 ? labelFont : (data.steps != null && data.steps >= 10000 ? smallFont : valueFont), data.steps == null ? "--" : formatSteps(data.steps), ink);
    }

    function formatSteps(n) {
        if (n < 1000) { return n.format("%d"); }
        return (n / 1000).toNumber().format("%d") + "," + (n % 1000).format("%03d");
    }

    function drawWeather(dc, x, y, kind) {
        var color = data.weatherStale ? copper : cyan;
        paint(dc, color, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        if (kind == "sun") {
            if (data.solarLabel.find("RISE") != null) {
                trace(dc, [[x - 4, y - 11], [x - 10, y - 7], [x - 12, y],
                    [x - 9, y + 8], [x - 2, y + 11], [x + 6, y + 8], [x + 10, y + 3],
                    [x + 3, y + 4], [x - 3, y], [x - 5, y - 6], [x - 4, y - 11]], color, 2);
            } else {
                dc.drawCircle(x, y, 7);
                for (var r = 0; r < 8; r += 1) { radial(dc, x, y, 11, 14, r * 45, color, 2); }
            }
        } else if (kind == "wind") {
            trace(dc, [[x - 14, y - 5], [x + 7, y - 5], [x + 10, y - 8], [x + 8, y - 11], [x + 5, y - 11]], color, 2);
            trace(dc, [[x - 10, y + 1], [x + 14, y + 1], [x + 16, y + 4], [x + 13, y + 7]], color, 2);
            stroke(dc, x - 14, y + 7, x + 5, y + 7, color, 2);
        } else if (kind == "fog") {
            stroke(dc, x - 14, y - 5, x + 14, y - 5, color, 2);
            stroke(dc, x - 10, y + 1, x + 10, y + 1, color, 2);
            stroke(dc, x - 14, y + 7, x + 14, y + 7, color, 2);
        } else {
            if (kind == "partly") {
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
            if (kind == "rain") {
                stroke(dc, x - 7, y + 11, x - 10, y + 16, color, 2);
                stroke(dc, x + 2, y + 11, x - 1, y + 16, color, 2);
                stroke(dc, x + 11, y + 11, x + 8, y + 16, color, 2);
            } else if (kind == "storm") {
                trace(dc, [[x + 3, y + 9], [x - 2, y + 15], [x + 5, y + 15], [x, y + 16]], color, 2);
            } else if (kind == "snow") {
                stroke(dc, x, y + 10, x, y + 16, color, 2);
                stroke(dc, x - 4, y + 12, x + 4, y + 17, color, 2);
                stroke(dc, x - 4, y + 17, x + 4, y + 12, color, 2);
            }
        }
        dc.setPenWidth(1);
        if (kind == "unknown" || data.weatherStale) {
            stroke(dc, x - 17, y + 16, x + 17, y - 17, copper, 2);
        }
    }

    function drawSolar(dc) {
        var x = 247;
        var y = 295;
        var up = data.solarLabel.find("RISE") != null;
        var color = data.solarTime == "--:--" ? 0x777F70 : (up ? 0x27645D : 0xA04D30);
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
        if (data.solarTime != "--:--") {
            var tipY = up ? y - 12 : y + 10;
            var baseY = up ? tipY + 5 : tipY - 5;
            stroke(dc, x + 16, up ? y - 12 : y + 1, x + 16, up ? y - 3 : y + 10, color, 2);
            stroke(dc, x + 12, baseY, x + 16, tipY, color, 2);
            stroke(dc, x + 20, baseY, x + 16, tipY, color, 2);
        }
        // "5:03 PM" needs the Label font to fit the plate; 24-hour and "--:--" use Small.
        if (data.solarTime.length() > 5) {
            text(dc, 307, 281, labelFont, data.solarTime, 0x183B3B);
        } else {
            text(dc, 307, 278, smallFont, data.solarTime, 0x183B3B);
        }
        if (data.solarLabel.find("*") != null) {
            paint(dc, copper, Graphics.COLOR_TRANSPARENT);
            dc.drawCircle(340, 307, 3);
        }
    }
}
