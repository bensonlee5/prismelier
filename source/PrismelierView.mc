using Toybox.Application;
using Toybox.Graphics;
using Toybox.Math;
using Toybox.System;
using Toybox.Time;
using Toybox.WatchUi;

// 416px FR265 only. All industrial artwork is drawn from vector primitives.
// No on-face branding or word labels: icons, numbers and essential units only.
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

    function initialize() {
        WatchFace.initialize();
        data = new PrismelierData();
        reloadSettings();
    }

    function onLayout(dc) {
        timeFont = WatchUi.loadResource(Rez.Fonts.Time);
        valueFont = WatchUi.loadResource(Rez.Fonts.Value);
        smallFont = WatchUi.loadResource(Rez.Fonts.Small);
        labelFont = WatchUi.loadResource(Rez.Fonts.Label);
        ambientFont = WatchUi.loadResource(Rez.Fonts.Ambient);
    }

    function reloadSettings() {
        data.loadSettings();
        var p = Application.Properties.getValue("Palette");
        green = p == 1 ? 0x90E6FF : 0xC7FF70;
        pink = p == 1 ? 0xFFB65D : 0xF474E8;
        cyan = p == 1 ? 0xD59DFF : 0x6BE4DE;
        data.refresh(true);
    }

    function onEnterSleep() {
        sleeping = true;
        WatchUi.requestUpdate();
    }

    function onExitSleep() {
        sleeping = false;
        data.refresh(true);
        WatchUi.requestUpdate();
    }

    function text(dc, x, y, font, s, color) {
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        dc.drawText(x, y, font, s, Graphics.TEXT_JUSTIFY_CENTER);
    }

    function stroke(dc, x1, y1, x2, y2, color, width) {
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
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
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
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
        drawArchitecture(dc);
        drawMachine(dc);
        drawBattery(dc);
        text(dc, 208, 77, timeFont, time, green);
        if (!data.is24Hour()) {
            text(dc, 208, 163, labelFont, clock.hour < 12 ? "AM" : "PM", ink);
        }
        drawTemperature(dc);
        drawVitals(dc);
    }

    function screw(dc, x, y, color) {
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x, y, 3);
        stroke(dc, x - 2, y + 1, x + 2, y - 1, 0x241620, 1);
    }

    function gear(dc, x, y, r, color) {
        for (var i = 0; i < 12; i += 1) {
            radial(dc, x, y, r - 2, r + 3, i * 30, color, 4);
        }
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(3);
        dc.drawCircle(x, y, r - 3);
        dc.setPenWidth(1);
        dc.drawCircle(x, y, r - 8);
        for (var a = 0; a < 3; a += 1) {
            radial(dc, x, y, 4, r - 8, a * 120 + 25, color, 3);
        }
        dc.setColor(0xD6D9BF, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x, y, 4);
        screw(dc, x, y, copper);
    }

    function trace(dc, points, color, width) {
        for (var i = 1; i < points.size(); i += 1) {
            stroke(dc, points[i - 1][0], points[i - 1][1], points[i][0], points[i][1], color, width);
        }
    }

    function junction(dc, x, y, color) {
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(x, y, 3);
        dc.fillCircle(x, y, 1);
    }

    function drawArchitecture(dc) {
        // Layered ceramic substrate: chip-like chamfers, never an analog ring.
        dc.setColor(0x071214, Graphics.COLOR_TRANSPARENT);
        dc.fillPolygon([[121, 25], [283, 25], [350, 87], [350, 168], [67, 168], [67, 87]]);
        trace(dc, [[111, 39], [137, 19], [279, 19], [301, 37]], 0x3D3433, 1);
        trace(dc, [[118, 43], [141, 25], [275, 25], [294, 43]], 0x175452, 1);
        trace(dc, [[137, 48], [151, 34], [264, 34], [280, 50]], 0x224142, 1);
        trace(dc, [[100, 48], [65, 81], [65, 108], [53, 120], [53, 143]], 0x6E4B3A, 1);
        trace(dc, [[109, 53], [74, 84], [74, 103], [62, 115]], 0x2F625C, 1);
        trace(dc, [[303, 49], [342, 84], [342, 105], [356, 119], [356, 143]], 0x335657, 1);
        trace(dc, [[309, 42], [350, 79], [350, 102], [365, 117]], 0x644154, 1);
        junction(dc, 53, 145, 0x916B49);
        junction(dc, 62, 116, 0x34877D);
        junction(dc, 356, 145, 0x4F958B);
        junction(dc, 366, 119, 0x86557A);
        // Microbridges route into the battery plate without touching the digits.
        dc.setColor(0x102226, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(149, 39, 104, 31, 7);
        stroke(dc, 158, 39, 241, 39, 0x3C6260, 1);
        for (var b = 0; b < 5; b += 1) {
            stroke(dc, 184 + b * 7, 29, 184 + b * 7, 34, 0x8B6544, 1);
        }
        junction(dc, 270, 57, 0x724060);
        trace(dc, [[253, 57], [264, 57]], 0x724060, 1);
        // Peripheral service channels have asymmetric joints, not hour ticks.
        trace(dc, [[34, 129], [23, 157], [23, 252], [32, 274]], 0x22433F, 1);
        trace(dc, [[29, 161], [29, 236]], 0x503949, 1);
        trace(dc, [[383, 130], [393, 163], [393, 249], [384, 272]], 0x4D3C2E, 1);
        trace(dc, [[387, 174], [387, 223], [381, 230]], 0x284D4D, 1);
        for (var n = 0; n < 4; n += 1) {
            stroke(dc, 20, 187 + n * 7, 28, 187 + n * 7, 0x326960, 1);
            stroke(dc, 388, 240 + n * 6, 394, 240 + n * 6, 0x6F494D, 1);
        }
        // Deeply engraved lower backplane keeps the heart/steps row uncluttered.
        dc.setColor(0x080F13, Graphics.COLOR_TRANSPARENT);
        dc.fillPolygon([[71, 312], [345, 312], [335, 352], [292, 374], [123, 374], [82, 352]]);
        trace(dc, [[70, 315], [76, 348], [120, 373], [158, 373], [171, 386], [203, 386]], 0x6B4839, 1);
        trace(dc, [[78, 351], [122, 379], [157, 379]], 0x263D3D, 1);
        trace(dc, [[346, 315], [340, 349], [299, 373], [260, 373], [247, 386], [216, 386]], 0x295F5D, 1);
        trace(dc, [[333, 356], [297, 379], [261, 379]], 0x69465B, 1);
        junction(dc, 204, 386, 0xA16E4C);
        junction(dc, 215, 386, 0x4B9D95);
        for (var f = 0; f < 7; f += 1) {
            stroke(dc, 175 + f * 11, 364, 181 + f * 11, 364, 0x334945, 1);
        }
        trace(dc, [[92, 360], [121, 367], [150, 367]], 0x243F42, 1);
        trace(dc, [[324, 361], [295, 367], [270, 367]], 0x3F314C, 1);
        screw(dc, 90, 348, 0x75513D);
        screw(dc, 326, 348, 0x365E59);
    }

    function drawMachine(dc) {
        // No clock indices or analog chapter ring. The perimeter stays quiet.
        // A split ceramic housing carries offset copper capillaries.
        dc.setColor(0x122325, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(45, 184, 326, 110, 17);
        dc.setColor(0x344741, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(45, 184, 326, 110, 17);
        for (var side = 0; side < 2; side += 1) {
            var x = side == 0 ? 42 : 374;
            stroke(dc, x, 207, x, 262, 0x5D3527, 7);
            stroke(dc, x - 1, 207, x - 1, 262, copper, 2);
            for (var k = 0; k < 6; k += 1) {
                stroke(dc, x - 5, 214 + k * 8, x + 5, 214 + k * 8, 0xB56942, 2);
            }
        }
        // Exposed violet/cyan gearing lives inside the machine, never as indices.
        gear(dc, 67, 184, 11, pink);
        gear(dc, 349, 184, 11, cyan);
        screw(dc, 59, 282, copper);
        screw(dc, 357, 282, copper);
        // A porcelain insert is deliberately paired with violet timber and
        // petrol enamel. Its irregular copper join is the material signature.
        dc.setColor(0x050E12, Graphics.COLOR_TRANSPARENT);
        dc.fillPolygon([[224, 249], [344, 249], [352, 256], [347, 286], [221, 286], [217, 278]]);
        dc.setColor(0xD6D9BF, Graphics.COLOR_TRANSPARENT);
        dc.fillPolygon([[224, 246], [344, 246], [352, 253], [347, 283], [221, 283], [217, 275]]);
        stroke(dc, 227, 248, 341, 248, 0xF5F5DB, 1);
        stroke(dc, 224, 246, 217, 275, copper, 2);
        stroke(dc, 217, 275, 221, 283, copper, 2);
        stroke(dc, 81, 288, 101, 288, 0x74ACA0, 1);
        // Inlaid timber circuits meet ceramic at the bottom of the instrument.
        stroke(dc, 84, 288, 105, 300, 0x805745, 2);
        stroke(dc, 105, 300, 162, 300, 0x805745, 2);
        stroke(dc, 253, 300, 310, 300, 0x487B72, 2);
        stroke(dc, 310, 300, 331, 288, 0x487B72, 2);
        screw(dc, 162, 300, pink);
        screw(dc, 253, 300, cyan);
    }

    function drawBattery(dc) {
        dc.setColor(cyan, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(162, 51, 17, 10, 2);
        dc.fillRectangle(179, 54, 2, 4);
        if (data.battery != null) {
            dc.fillRectangle(165, 54, (11 * clamp(data.battery, 0, 100) / 100).toNumber(), 4);
        }
        var s = data.battery == null ? "--%" : data.battery.format("%d") + "%";
        text(dc, 217, 42, smallFont, s, data.battery != null && data.battery <= 15 ? pink : cyan);
    }

    function drawTemperature(dc) {
        // Linear temperature bar in a violet woodgrain/copper instrument frame.
        dc.setColor(0x452744, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(56, 192, 304, 54, 10);
        for (var grain = 0; grain < 5; grain += 1) {
            stroke(dc, 71, 197 + grain * 10, 345, 199 + grain * 10, grain % 2 == 0 ? 0x85506D : 0x5D3854, 1);
        }
        dc.setColor(copper, Graphics.COLOR_TRANSPARENT);
        dc.drawRoundedRectangle(56, 192, 304, 54, 10);
        stroke(dc, 71, 193, 344, 193, 0xF2BF8C, 1);
        stroke(dc, 71, 245, 344, 245, 0x3E211E, 2);
        screw(dc, 64, 201, copper);
        screw(dc, 352, 201, copper);
        screw(dc, 64, 237, copper);
        screw(dc, 352, 237, copper);
        dc.setColor(0x091B23, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(73, 209, 270, 19, 4);
        var fahrenheit = data.isFahrenheit();
        var low = fahrenheit ? 0 : -20;
        var high = fahrenheit ? 120 : 40;
        var val = data.temperatureC;
        if (val != null && fahrenheit) { val = val * 9.0 / 5.0 + 32.0; }
        if (val != null) {
            var f = clamp((val - low).toFloat() / (high - low), 0.0, 1.0);
            var width = (262 * f).toNumber();
            if (width > 0) {
                dc.setColor(data.weatherStale ? 0x80665C : pink, Graphics.COLOR_TRANSPARENT);
                dc.fillRoundedRectangle(77, 213, width, 11, 3);
                stroke(dc, 79, 214, 77 + width, 214, data.weatherStale ? copper : 0xFFC9FA, 1);
            }
            // A square piston instead of a needle. Endpoint clamped, reading exact.
            dc.setColor(ink, Graphics.COLOR_TRANSPARENT);
            dc.fillRectangle(75 + width, 209, 4, 19);
        }
        for (var t = 0; t <= 12; t += 1) {
            var tx = 77 + (262 * t / 12).toNumber();
            stroke(dc, tx, 202, tx, t % 3 == 0 ? 207 : 205, copper, 1);
            stroke(dc, tx, 232, tx, t % 3 == 0 ? 238 : 235, copper, 1);
        }
        var reading = val == null ? "--" : Math.round(val).toNumber().format("%d");
        drawWeather(dc, 94, 265, data.weatherKind);
        text(dc, 165, 247, valueFont, reading + (fahrenheit ? "°F" : "°C"), ink);
        if (data.weatherStale) {
            // Small crossed ring = stale/unknown weather; explained in README.
            dc.setColor(copper, Graphics.COLOR_TRANSPARENT);
            dc.drawCircle(208, 280, 4);
            stroke(dc, 205, 283, 211, 277, copper, 1);
        }
        drawSolar(dc);
    }

    function drawVitals(dc) {
        var x = 101;
        var y = 332;
        dc.setColor(pink, Graphics.COLOR_TRANSPARENT);
        dc.fillCircle(x - 4, y - 3, 5);
        dc.fillCircle(x + 4, y - 3, 5);
        dc.fillPolygon([[x - 9, y], [x + 9, y], [x, y + 9]]);
        text(dc, 149, 315, valueFont, data.heartRate == null ? "--" : data.heartRate.format("%d"), ink);
        dc.setColor(cyan, Graphics.COLOR_TRANSPARENT);
        dc.fillEllipse(220, 322, 6, 11);
        dc.fillEllipse(229, 328, 6, 11);
        dc.fillCircle(223, 318, 2);
        dc.fillCircle(232, 324, 2);
        text(dc, 288, 315, data.steps != null && data.steps >= 10000 ? smallFont : valueFont, data.steps == null ? "--" : formatSteps(data.steps), ink);
    }

    function formatSteps(n) {
        if (n < 1000) { return n.format("%d"); }
        return (n / 1000).toNumber().format("%d") + "," + (n % 1000).format("%03d");
    }

    function drawWeather(dc, x, y, kind) {
        var color = data.weatherStale ? copper : cyan;
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        if (kind == "wind") {
            stroke(dc, x - 14, y - 5, x + 8, y - 5, color, 2);
            stroke(dc, x - 9, y + 1, x + 14, y + 1, color, 2);
            stroke(dc, x - 14, y + 7, x + 5, y + 7, color, 2);
            dc.drawCircle(x + 9, y - 8, 3);
            dc.drawCircle(x + 14, y + 4, 3);
        } else if (kind == "sun" && data.solarLabel.find("RISE") != null) {
            dc.fillCircle(x, y, 10);
            dc.setColor(0x122325, Graphics.COLOR_TRANSPARENT);
            dc.fillCircle(x + 5, y - 4, 9);
            stroke(dc, x + 14, y - 9, x + 14, y - 3, color, 1);
            stroke(dc, x + 11, y - 6, x + 17, y - 6, color, 1);
        } else if (kind == "sun") {
            dc.drawCircle(x, y, 7);
            for (var i = 0; i < 8; i += 1) { radial(dc, x, y, 10, 14, i * 45, color, 1); }
        } else if (kind == "fog") {
            stroke(dc, x - 14, y - 5, x + 14, y - 5, color, 2);
            stroke(dc, x - 10, y + 1, x + 10, y + 1, color, 2);
            stroke(dc, x - 14, y + 7, x + 14, y + 7, color, 2);
        } else {
            if (kind == "partly") {
                dc.setColor(copper, Graphics.COLOR_TRANSPARENT);
                dc.fillCircle(x + 8, y - 9, 7);
                radial(dc, x + 8, y - 9, 10, 12, 270, copper, 1);
                radial(dc, x + 8, y - 9, 10, 12, 315, copper, 1);
                radial(dc, x + 8, y - 9, 10, 12, 0, copper, 1);
                dc.setColor(color, Graphics.COLOR_TRANSPARENT);
            }
            dc.fillCircle(x - 8, y, 6);
            dc.fillCircle(x, y - 5, 9);
            dc.fillCircle(x + 9, y, 6);
            dc.fillRectangle(x - 9, y, 19, 5);
            if (kind == "rain" || kind == "storm") {
                stroke(dc, x - 5, y + 9, x - 9, y + 14, color, 2);
                stroke(dc, x + 6, y + 9, x + 2, y + 14, color, 2);
                if (kind == "storm") {
                    stroke(dc, x + 15, y - 7, x + 10, y + 1, pink, 2);
                    stroke(dc, x + 10, y + 1, x + 16, y + 1, pink, 2);
                    stroke(dc, x + 16, y + 1, x + 12, y + 8, pink, 2);
                }
            } else if (kind == "snow") {
                dc.fillCircle(x - 6, y + 12, 2);
                dc.fillCircle(x + 6, y + 12, 2);
            }
        }
        if (kind == "unknown" || data.weatherStale) {
            stroke(dc, x - 16, y + 15, x + 16, y - 16, Graphics.COLOR_BLACK, 5);
            stroke(dc, x - 16, y + 15, x + 16, y - 16, copper, 2);
        }
    }

    function drawSolar(dc) {
        var x = 240;
        var y = 269;
        var up = data.solarLabel.find("RISE") != null;
        var color = data.solarTime == "--:--" ? 0x777F70 : (up ? 0x27645D : 0xA04D30);
        var sunY = up ? y - 5 : y + 2;
        dc.setColor(color, Graphics.COLOR_TRANSPARENT);
        dc.drawCircle(x, sunY, 8);
        dc.setColor(0xD6D9BF, Graphics.COLOR_TRANSPARENT);
        dc.fillRectangle(x - 10, y + 1, 20, 14);
        stroke(dc, x - 14, y, x + 14, y, color, 2);
        radial(dc, x, sunY, 11, 14, 220, color, 1);
        radial(dc, x, sunY, 11, 14, 270, color, 1);
        radial(dc, x, sunY, 11, 14, 320, color, 1);
        if (data.solarTime != "--:--") {
            // Sunrise: rising sun + upward arrow. Sunset: sinking sun + down.
            var tipY = up ? y - 12 : y + 10;
            var baseY = up ? tipY + 5 : tipY - 5;
            stroke(dc, x + 16, up ? y - 12 : y + 1, x + 16, up ? y - 3 : y + 10, color, 2);
            stroke(dc, x + 12, baseY, x + 16, tipY, color, 2);
            stroke(dc, x + 20, baseY, x + 16, tipY, color, 2);
        }
        text(dc, 302, 250, smallFont, data.solarTime, 0x183B3B);
        if (data.solarLabel.find("*") != null) {
            dc.setColor(copper, Graphics.COLOR_TRANSPARENT);
            dc.drawCircle(345, 278, 3);
        }
    }
}
