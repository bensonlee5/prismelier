"""Asset/source-contract QA, not a Monkey C runtime or Garmin simulator.

Run: python -m unittest discover -s tests -v
Optional: CONNECTIQ_SDK=/path/to/official/sdk enables API-symbol and parser checks.
Pillow enables exhaustive font-asset AOD checks; no SDK or Pillow is required
for the structural tests. Nothing is downloaded or installed by these tests.
"""
from pathlib import Path
import html
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib
import xml.etree.ElementTree as ET

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError:
    Image = ImageChops = ImageFilter = None

ROOT = Path(__file__).resolve().parents[1]
NS = {"iq": "http://www.garmin.com/xml/connectiq"}
SOURCE = ROOT / "source"
SDK_VALUE = (os.environ.get("CONNECTIQ_SDK") or os.environ.get("CIQ_SDK") or
             os.environ.get("CIQ_HOME"))
SDK = Path(SDK_VALUE).expanduser() if SDK_VALUE else None


def source_text(name):
    return (SOURCE / name).read_text(encoding="utf-8")

def without_comments(text):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", text, flags=re.S)

def font_metadata(name):
    path = ROOT / "resources" / "fonts" / (name + ".fnt")
    result = {"glyphs": {}, "pages": {}, "path": path}
    for line in path.read_text(encoding="utf-8").splitlines():
        tokens = shlex.split(line)
        if not tokens:
            continue
        values = dict(token.split("=", 1) for token in tokens[1:])
        if tokens[0] == "char":
            values = {key: int(value) for key, value in values.items()}
            result["glyphs"][values["id"]] = values
        elif tokens[0] == "page":
            result["pages"][int(values["id"])] = path.parent / values["file"]
        elif tokens[0] in ("common", "chars"):
            result[tokens[0]] = {key: int(value) for key, value in values.items()}
    return result

def png_header(path):
    with path.open("rb") as handle:
        header = handle.read(33)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise AssertionError("Not a PNG with an IHDR header: " + str(path))
    return struct.unpack(">IIBBBBB", header[16:29])

def png_chunks(path):
    """Read PNG chunks without Pillow, including indexed-image transparency."""
    raw = path.read_bytes()
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError("Not a PNG: " + str(path))
    offset = 8
    result = []
    while offset + 12 <= len(raw):
        length = struct.unpack(">I", raw[offset:offset + 4])[0]
        kind = raw[offset + 4:offset + 8]
        end = offset + 12 + length
        if end > len(raw):
            raise AssertionError("Truncated PNG chunk: " + str(path))
        data = raw[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", raw[offset + 8 + length:end])[0]
        if zlib.crc32(kind + data) != crc:
            raise AssertionError("Invalid PNG chunk CRC: " + str(path))
        result.append((kind, data))
        offset = end
        if kind == b"IEND":
            break
    if offset != len(raw) or not result or result[-1][0] != b"IEND":
        raise AssertionError("PNG missing IEND or has trailing data: " + str(path))
    return result

def clock_text(minute, use_24_hour):
    """Independent test input generation, not execution of formatTime()."""
    hour, minute = divmod(minute, 60)
    return (f"{hour:02d}:{minute:02d}" if use_24_hour else
            f"{hour % 12 or 12}:{minute:02d}")


def argument_count(text, opening):
    """Count top-level arguments from an observed '('; honor strings/brackets."""
    stack = [")"]
    pairs = {"(": ")", "[": "]", "{": "}"}
    quote = None
    escaped = False
    count = 0
    content = False
    for char in text[opening + 1:]:
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            continue
        if char in ('"', "'"):
            quote = char
            content = True
        elif char in pairs:
            stack.append(pairs[char])
            content = True
        elif char == stack[-1]:
            stack.pop()
            if not stack:
                return count + int(content)
        elif char == "," and len(stack) == 1:
            count += 1
        elif not char.isspace():
            content = True
    raise AssertionError("Unclosed argument list")


class ProjectStructureTests(unittest.TestCase):
    def test_manifest_target_and_minimum_api(self):
        manifest = ET.parse(ROOT / "manifest.xml").getroot()
        app = manifest.find("iq:application", NS)
        self.assertIsNotNone(app)
        self.assertEqual(app.attrib["type"], "watchface")
        self.assertEqual(app.attrib["entry"], "PrismelierApp")
        self.assertEqual(app.attrib["minApiLevel"], "4.2.0")
        self.assertEqual([p.attrib["id"] for p in app.findall("iq:products/iq:product", NS)],
                         ["fr265"])
        self.assertRegex(app.attrib["id"], r"^[0-9a-f]{32}$")

    def test_permissions_and_no_active_sensor_or_network_calls(self):
        manifest = ET.parse(ROOT / "manifest.xml").getroot()
        permissions = {p.attrib["id"] for p in manifest.findall(".//iq:uses-permission", NS)}
        self.assertEqual(permissions, {"SensorHistory", "Positioning", "ComplicationSubscriber"})
        code = without_comments("\n".join(p.read_text() for p in SOURCE.glob("*.mc")))
        for forbidden in ("Toybox.Communications", "makeWebRequest", "makeImageRequest",
                          "enableLocationEvents", "enableSensorEvents", "registerSensorDataListener"):
            self.assertNotIn(forbidden, code)
        self.assertNotRegex(code, r"using\s+Toybox\.Sensor\s*;")

    def test_resource_files_and_references(self):
        ids = {"Strings": set(), "Properties": set(), "Fonts": set(), "Drawables": set()}
        category = {"string": "Strings", "property": "Properties", "font": "Fonts", "bitmap": "Drawables"}
        xml_paths = sorted((ROOT / "resources").rglob("*.xml"))
        self.assertTrue(xml_paths)
        for path in xml_paths:
            for element in ET.parse(path).getroot().iter():
                if element.tag in category:
                    group = ids[category[element.tag]]
                    self.assertNotIn(element.attrib["id"], group)
                    group.add(element.attrib["id"])
                if "filename" in element.attrib:
                    target = (path.parent / element.attrib["filename"]).resolve()
                    self.assertTrue(target.is_relative_to(ROOT.resolve()))
                    self.assertTrue(target.is_file(), str(target))
        text = "\n".join(p.read_text() for p in xml_paths + [ROOT / "manifest.xml"])
        for group, name in re.findall(r"@(Strings|Properties|Fonts|Drawables)\.([A-Za-z0-9_]+)", text):
            self.assertIn(name, ids[group], group + "." + name)
        code = "\n".join(p.read_text() for p in SOURCE.glob("*.mc"))
        for group, name in re.findall(r"Rez\.(Strings|Properties|Fonts|Drawables)\.([A-Za-z0-9_]+)", code):
            self.assertIn(name, ids[group], group + "." + name)

    def test_settings_contract(self):
        properties = ET.parse(ROOT / "resources/settings/properties.xml").getroot()
        values = {p.attrib["id"]: p.text for p in properties}
        self.assertEqual(values, {"Palette": "1", "TimeFormat": "0", "TemperatureUnits": "2"})
        settings = ET.parse(ROOT / "resources/settings/settings.xml").getroot()
        expected = {"Palette": {"0", "1", "2", "3"}, "TimeFormat": {"0", "1", "2"},
                    "TemperatureUnits": {"0", "1", "2"}}
        for setting in settings:
            key = setting.attrib["propertyKey"].split(".")[-1]
            self.assertEqual({entry.attrib["value"] for entry in setting.findall(".//listEntry")}, expected.pop(key))
        self.assertFalse(expected)
        self.assertIn('palette = readChoice("Palette", 3);', source_text("PrismelierData.mc"))

    def test_palette_source_matches_json_and_keeps_ambient_color(self):
        themes = json.loads((ROOT / "resources/themes.json").read_text(encoding="utf-8"))
        self.assertEqual([theme["name"] for theme in themes],
                         ["Reactor", "Foundry", "Porcelain", "Nocturne"])
        base = themes[0]["colors"]
        self.assertTrue(base)
        for theme in themes:
            self.assertEqual(set(theme["colors"]), set(base))
            for original, mapped in theme["colors"].items():
                self.assertRegex(original, r"^[0-9A-F]{6}$")
                self.assertRegex(mapped, r"^[0-9A-F]{6}$")
            self.assertEqual(theme["colors"]["606775"], "606775")
            for ambient in ("84644C", "A09785"):
                self.assertEqual(theme["colors"][ambient], ambient)
            self.assertEqual(theme["colors"].get("000000", "000000"), "000000")
        self.assertTrue(all(key == value for key, value in base.items()))
        palette = without_comments(source_text("PrismelierPalette.mc"))
        self.assertIn("module PrismelierPalette", palette)
        self.assertRegex(palette, r"function\s+color\(value, theme\)")
        self.assertIn("if (theme == 0) { return value; }", palette)
        blocks = re.findall(r"case 0x([0-9A-F]{6}):(.*?)break;", palette, re.S)
        self.assertEqual(len(blocks), len(base))
        self.assertEqual({key for key, _ in blocks}, set(base))
        for original, body in blocks:
            entries = re.findall(r"if \(theme == ([1-3])\) \{ return 0x([0-9A-F]{6}); \}", body)
            self.assertEqual(len(entries), 3)
            self.assertEqual(dict(entries), {str(i): themes[i]["colors"][original] for i in range(1, 4)})
        self.assertRegex(palette, r"}\s*return value;\s*}\s*}\s*$")
        view = without_comments(source_text("PrismelierView.mc"))
        self.assertTrue(set(re.findall(r"0x([0-9A-F]{6})\b", view)) <= set(base),
                        "Every literal artwork color must be in the theme map")
        self.assertIn("theme = data.palette;", view)
        # Mapped colors are memoized per theme; settings changes clear the cache.
        self.assertIn("c = PrismelierPalette.color(foreground, theme);", view)
        self.assertIn("dc.setColor(c, background);", view)
        reload = view.split("function reloadSettings()", 1)[1].split("function refreshTexture", 1)[0]
        self.assertLess(reload.index("theme = data.palette;"), reload.index("colors = {};"))
        self.assertEqual(view.count("dc.setColor("), 1, "Artwork bypasses the palette helper")
        print(f"\nPalette source audit: {len(themes)} themes x {len(base)} color entries match JSON; "
              "ambient ink and black remain unchanged")

    def test_font_pages_geometry_and_rgb_storage(self):
        fonts = ET.parse(ROOT / "resources/fonts/fonts.xml").getroot()
        for font in fonts:
            with self.subTest(font=font.attrib["id"]):
                self.assertEqual(font.attrib.get("antialias"), "true")
                data = font_metadata(font.attrib["id"])
                self.assertEqual(len(data["glyphs"]), data["chars"]["count"])
                self.assertEqual(data["common"]["pages"], len(data["pages"]))
                for page in data["pages"].values():
                    width, height, depth, color_type, compression, filtering, interlace = png_header(page)
                    self.assertEqual((width, height), (data["common"]["scaleW"], data["common"]["scaleH"]))
                    self.assertEqual((depth, color_type), (8, 2), "Font atlases must be RGB intensity PNGs, without alpha")
                for glyph in data["glyphs"].values():
                    self.assertIn(glyph["page"], data["pages"])
                    self.assertGreater(glyph["xadvance"], 0)
                    self.assertGreater(glyph["width"], 0)
                    self.assertGreater(glyph["height"], 0)
                    self.assertGreaterEqual(glyph["x"], 0)
                    self.assertGreaterEqual(glyph["y"], 0)
                    self.assertLessEqual(glyph["x"] + glyph["width"], data["common"]["scaleW"])
                    self.assertLessEqual(glyph["y"] + glyph["height"], data["common"]["scaleH"])

    def test_foundry_texture_resource_is_one_opaque_indexed_416_bitmap(self):
        path = ROOT / "resources/textures/textures.xml"
        root = ET.parse(path).getroot()
        self.assertEqual(root.tag, "resources")
        self.assertEqual(len(root), 1)
        bitmap = root[0]
        self.assertEqual(bitmap.tag, "bitmap")
        self.assertEqual(bitmap.attrib, {
            "id": "FoundryBackground", "filename": "foundry-background-indexed.png",
            "packingFormat": "default", "automaticPalette": "true",
            "dithering": "none", "compress": "true",
        })
        # monkeyc rejects an explicit <palette> alongside automaticPalette="true";
        # opacity is enforced by the source PNG (no tRNS) checked below.
        self.assertEqual(len(bitmap), 0)
        texture = path.parent / bitmap.attrib["filename"]
        self.assertEqual(png_header(texture), (416, 416, 8, 3, 0, 0, 0))
        chunks = png_chunks(texture)
        kinds = [kind for kind, _ in chunks]
        self.assertNotIn(b"tRNS", kinds, "Indexed source must have no transparent palette entries")
        self.assertEqual(kinds.count(b"PLTE"), 1)
        palette = next(data for kind, data in chunks if kind == b"PLTE")
        self.assertEqual(len(palette) % 3, 0)
        self.assertLessEqual(len(palette) // 3, 256)
        self.assertGreater(len(palette), 0)
        self.assertIn(b"IDAT", kinds)
        decoded = zlib.decompress(b"".join(data for kind, data in chunks if kind == b"IDAT"))
        self.assertEqual(len(decoded), 416 * (416 + 1))
        self.assertTrue(all(decoded[row * 417] in range(5) for row in range(416)))
        print(f"\nFoundry texture: 416x416, {len(palette) // 3} palette entries, opaque; "
              f"source PNG {texture.stat().st_size:,} bytes (not runtime RAM)")

    def test_font_glyph_coverage_including_stale_marker(self):
        requirements = {
            "Time": "0123456789:", "Ambient": "0123456789:",
            "Value": "0123456789-,.%°CF", "Small": "0123456789-:°CFAP%,",
            "Label": " ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-:.,%°/*",
        }
        # Cover every uppercase display literal in the data and view sources.
        display_literals = re.findall(r'"([A-Z0-9 *:/.,%-]+)"',
            source_text("PrismelierData.mc") + source_text("PrismelierView.mc"))
        requirements["Label"] += "".join(display_literals)
        for name, characters in requirements.items():
            glyphs = font_metadata(name)["glyphs"]
            missing = sorted(set(characters) - {chr(code) for code in glyphs})
            self.assertEqual(missing, [], name + " missing glyphs")


class DataSourceContractTests(unittest.TestCase):
    """Intentional static guards; they do not execute Monkey C API behavior."""
    def setUp(self):
        self.code = without_comments(source_text("PrismelierData.mc"))

    def test_freshness_thresholds_and_timestamped_heart_rate(self):
        for name, value in (("WEATHER_STALE_SECONDS", 7200),
                            ("WEATHER_EXPIRE_SECONDS", 86400),
                            ("HEART_RATE_MAX_AGE_SECONDS", 120)):
            self.assertRegex(self.code, rf"const\s+{name}\s*=\s*{value}\s*;")
        self.assertIn("SensorHistory.getHeartRateHistory", self.code)
        self.assertIn("new Time.Duration(HEART_RATE_MAX_AGE_SECONDS)", self.code)
        self.assertIn("SensorHistory.ORDER_NEWEST_FIRST", self.code)
        self.assertIn("sample.when.value()", self.code)
        self.assertIn("sample.data != ActivityMonitor.INVALID_HR_SAMPLE", self.code)
        self.assertIn("Activity.getActivityInfo().currentHeartRate", self.code)
        self.assertIn('weatherLabel = "AGE UNKNOWN"', self.code)
        self.assertIn('weatherLabel = "WX EXPIRED"', self.code)
        self.assertIn('weatherLabel = "CHECK TIME"', self.code)
        self.assertLess(self.code.index("seconds - _heartRateAt > HEART_RATE_MAX_AGE_SECONDS"),
                        self.code.index("if (force || minute != _lastRefreshMinute)"))

    def test_time_and_units_follow_explicit_or_device_settings(self):
        for fragment in ('_timeFormat == 1', '_timeFormat == 2',
                         'System.getDeviceSettings().is24Hour',
                         '_temperatureUnits == 1', '_temperatureUnits == 2',
                         'System.getDeviceSettings().temperatureUnits == System.UNIT_STATUTE',
                         'hour % 12', 'if (h == 0) { h = 12; }'):
            self.assertIn(fragment, self.code)
        self.assertIn('hour.format("%02d")', self.code)
        self.assertIn('minute.format("%02d")', self.code)

    def test_humidity_shares_weather_age_and_body_battery_is_separate(self):
        self.assertIn("_weatherHumidity = wx.relativeHumidity;", self.code)
        display = self.code.split("private function updateWeatherDisplay", 1)[1].split("private function setWeatherCondition", 1)[0]
        self.assertLess(display.index("humidity = null;"), display.index("if (!_weatherPresent)"))
        self.assertLess(display.index("age >= WEATHER_EXPIRE_SECONDS"), display.index("humidity = _weatherHumidity;"))
        self.assertIn("_weatherHumidity >= 0 && _weatherHumidity <= 100", display)
        view = without_comments(source_text("PrismelierView.mc"))
        self.assertIn("getBodyBatteryHistory", self.code)
        self.assertIn("drawBodyBattery(dc);", view)
        humidity = view.split("function drawWeatherRail(dc,", 1)[1].split("function drawTemperature", 1)[0]
        self.assertIn('34.0 * clamp(value, 0, 100) / 100.0', humidity)
        self.assertIn('if (value != null)', humidity)
        self.assertIn('dc.fillRectangle(x - 2.5, 244, 5, 34);', humidity)
        self.assertIn('stroke(dc, x - 3, 257, x + 3, 265, muted, 1);', humidity)
        self.assertIn("data.weatherStale ? copper : fillColor", humidity)
        self.assertIn('data.battery.format("%d") + "%"', view)

    def test_solar_location_timezone_selection_and_expiry_contract(self):
        self.assertIn("wx.observationLocationPosition", self.code)
        self.assertNotIn("new Position.Location", self.code)
        self.assertIn("Time.today().add(new Time.Duration(43200))", self.code)
        self.assertIn("today.add(new Time.Duration(86400))", self.code)
        for event in ("Sunrise", "Sunset"):
            for day in ("today", "tomorrow"):
                self.assertIn(f"Weather.get{event}(_location, {day})", self.code)
        self.assertIn("candidate.value() > nowSeconds", self.code)
        self.assertIn("candidate.value() < best.value()", self.code)
        self.assertIn("Gregorian.info(best, Time.FORMAT_SHORT)", self.code)
        self.assertNotIn("Gregorian.utcInfo", self.code)
        self.assertNotIn("timeZoneOffset", self.code)
        self.assertIn("nowSeconds - _locationAt >= WEATHER_EXPIRE_SECONDS", self.code)
        self.assertIn('solarLabel += "*"', self.code)
        self.assertIn('solarTime = "--:--"', self.code)

    def test_sleep_branch_is_sparse_time_and_calendar(self):
        view = without_comments(source_text("PrismelierView.mc"))
        branch = view.split("if (sleeping) {", 1)[1].split("data.refresh(false);", 1)[0]
        self.assertEqual(len(re.findall(r"\btext\(", branch)), 2)
        self.assertIn("ambientFont, time", branch)
        self.assertIn("return;", branch)
        self.assertNotIn("data.refresh(", branch)
        self.assertNotRegex(branch, r"\bdraw[A-Z]")
        self.assertNotIn("Timer", view)
        before_branch = view.split("function onUpdate(dc)", 1)[1].split("data.refresh(false);", 1)[0]
        self.assertIn("paint(dc, Graphics.COLOR_BLACK, Graphics.COLOR_BLACK)", before_branch)
        self.assertIn("dc.clear()", before_branch)
        # Background craftsmanship is awake-only. Guard its call site as well
        # as the sparse sleep body so later refactors cannot light it in AOD.
        update = view.split("function onUpdate(dc) {", 1)[1].split("\n    function ", 1)[0]
        self.assertLess(update.index("return;"), update.index("data.refresh(false);"))
        for method in ("drawArchitecture", "drawRobotics"):
            call = method + "(dc);"
            positions = [m.start() for m in re.finditer(re.escape(call), update)]
            self.assertTrue(positions)
            self.assertNotIn(method + "(", before_branch)
            self.assertTrue(all(update.index("data.refresh(false);") < p for p in positions))
            self.assertEqual(view.count(call), len(positions))

    def test_texture_reference_lifecycle_and_awake_only_draw(self):
        view = without_comments(source_text("PrismelierView.mc"))
        refresh = view.split("function refreshTexture()", 1)[1].split("function usesTexture()", 1)[0]
        self.assertIn("if (theme != 1)", refresh)
        self.assertIn("background = null;", refresh)
        self.assertIn("background == null", refresh)
        resource = "WatchUi.loadResource(Rez.Drawables.FoundryBackground)"
        self.assertEqual(refresh.count(resource), 1)
        self.assertEqual(view.count(resource), 1)
        self.assertIn("try {", refresh)
        self.assertRegex(refresh, r"catch\s*\(e\)\s*\{\s*background = null;")
        layout = view.split("function onLayout(dc)", 1)[1].split("function reloadSettings()", 1)[0]
        settings = view.split("function reloadSettings()", 1)[1].split("function refreshTexture()", 1)[0]
        self.assertIn("refreshTexture();", layout)
        self.assertIn("if (laidOut) { refreshTexture(); }", settings)
        self.assertIn("return theme == 1 && background != null;", view)
        update = view.split("function onUpdate(dc)", 1)[1].split("\n    function ", 1)[0]
        draw = "dc.drawBitmap(0, 0, background);"
        self.assertEqual(view.count(draw), 1)  # every awake update draws a complete frame
        self.assertLess(update.index("return;"), update.index(draw))
        self.assertLess(update.index("data.refresh(false);"), update.index(draw))
        self.assertNotIn("loadResource(", update)
        self.assertNotIn("refreshTexture(", update)
        self.assertNotRegex(view, r"\.get\s*\(")
        self.assertNotIn("BufferedBitmap", view)
        recovery = update.split(draw, 1)[1].split("} else {", 1)[0]
        self.assertIn("catch (e)", recovery)
        self.assertIn("background = null;", recovery)
        self.assertIn("paint(dc, Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);", recovery)
        self.assertLess(recovery.index("dc.clear();"), recovery.index("drawArchitecture(dc);"))
        for call in ("drawArchitecture(dc);", "drawRobotics(dc);", "drawMachine(dc);"):
            self.assertIn(call, recovery)


@unittest.skipUnless(Image is not None, "Pillow not installed; optional font-asset raster checks skipped")
class AmbientAssetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        view = source_text("PrismelierView.mc")
        cls.base_y, cls.step = map(int, re.search(r"var y = (\d+) \+ slot \* (\d+)", view).groups())
        cls.slots = int(re.search(r"var slot = .*? % (\d+);", view).group(1))
        cls.font = font_metadata("Ambient")
        with Image.open(cls.font["pages"][0]) as atlas:
            cls.atlas = atlas.convert("L")
        cls.width = cls.height = 416
        cls.circle_pixels = sum((x + .5 - 208) ** 2 + (y + .5 - 208) ** 2 <= 208 ** 2
                                for y in range(416) for x in range(416))

    def mask_for_text(self, text):
        # Use committed BMFont metrics and atlas, not a host system font.
        glyphs = self.font["glyphs"]
        width = sum(glyphs[ord(char)]["xadvance"] for char in text)
        local_height = self.font["common"]["lineHeight"] + 4
        result = Image.new("L", (416, local_height))
        # Union floor/ceil centering, then a 1px halo, conservatively covers
        # raster alignment uncertainty. This still is not Garmin rendering.
        for rounding in (math.floor, math.ceil):
            canvas = Image.new("L", result.size)
            x = (416 - width) / 2
            for char in text:
                glyph = glyphs[ord(char)]
                box = (glyph["x"], glyph["y"], glyph["x"] + glyph["width"],
                       glyph["y"] + glyph["height"])
                mask = self.atlas.crop(box)
                canvas.paste(mask, (rounding(x + glyph["xoffset"]), 2 + glyph["yoffset"]))
                x += glyph["xadvance"]
            result = ImageChops.lighter(result, canvas)
        return result.point([0] + [255] * 255).filter(ImageFilter.MaxFilter(3))

    def test_atlas_has_antialias_intensities(self):
        self.assertGreater(sum(self.atlas.histogram()[1:255]), 0)
        self.assertGreater(self.atlas.histogram()[255], 0)

    def test_every_minute_both_formats_under_ten_percent_and_disjoint_bands(self):
        union = Image.new("L", (416, self.font["common"]["lineHeight"] + 4))
        peak = 0
        peak_time = ""
        for mode in (True, False):
            for minute in range(1440):
                text = clock_text(minute, mode)
                mask = self.mask_for_text(text)
                lit = sum(mask.histogram()[1:])
                if lit > peak:
                    peak, peak_time = lit, text
                self.assertLess(lit / self.circle_pixels, .10, (text, mode, lit))
                union = ImageChops.lighter(union, mask)
        # Union of ALL times in each band is stronger than checking only
        # consecutive triplets: no displayed minute can overlap any other band.
        bands = []
        for slot in range(self.slots):
            canvas = Image.new("L", (416, 416))
            top = self.base_y + slot * self.step - 2
            canvas.paste(union, (0, top))
            self.assertEqual(sum(canvas.histogram()[1:]), sum(union.histogram()[1:]),
                             "Ambient pixels clipped at a screen edge")
            bounds = canvas.getbbox()
            for x in (bounds[0], bounds[2] - 1):
                for y in (bounds[1], bounds[3] - 1):
                    self.assertLessEqual((x + .5 - 208) ** 2 + (y + .5 - 208) ** 2, 208 ** 2)
            bands.append(canvas)
        self.assertEqual(self.slots, 3)
        for i in range(len(bands)):
            for j in range(i + 1, len(bands)):
                self.assertIsNone(ImageChops.multiply(bands[i], bands[j]).getbbox(), (i, j))
        print(f"\nAOD asset estimate: 2,880 clock strings x 3 bands; peak {peak} lit pixels "
              f"({peak / self.circle_pixels:.3%} of {self.circle_pixels} circular pixels), "
              f"at {peak_time}; includes 1px halo; no firmware claim")


@unittest.skipUnless(Image is not None, "Pillow not installed; optional texture safe-area check skipped")
class TextureAssetTests(unittest.TestCase):
    def test_meaningful_texture_pixels_inside_204px_safe_radius(self):
        root = ET.parse(ROOT / "resources/textures/textures.xml").getroot()
        path = ROOT / "resources/textures" / root[0].attrib["filename"]
        with Image.open(path) as source:
            self.assertEqual(source.size, (416, 416))
            self.assertEqual(source.mode, "P")
            self.assertNotIn("transparency", source.info)
            pixels = source.convert("RGB")
            max_distance_squared = 0
            meaningful = 0
            for y in range(416):
                for x in range(416):
                    # A dim near-black border is immaterial artwork; this is
                    # an asset-coordinate test, not hardware clipping proof.
                    if max(pixels.getpixel((x, y))) > 8:
                        meaningful += 1
                        distance_squared = (x + .5 - 208) ** 2 + (y + .5 - 208) ** 2
                        max_distance_squared = max(max_distance_squared, distance_squared)
                        self.assertLessEqual(distance_squared, 204 ** 2, (x, y))
            self.assertGreater(meaningful, 0)
            print(f"\nTexture safe area: {meaningful:,} pixels with max RGB > 8; "
                  f"maximum center-based radius {math.sqrt(max_distance_squared):.4f}px <= 204px")


@unittest.skipUnless(SDK is not None, "Set CONNECTIQ_SDK, CIQ_SDK, or CIQ_HOME for optional official SDK checks")
class OfficialSdkChecks(unittest.TestCase):
    def test_texture_xml_options_and_fr265_memory_against_official_sdk(self):
        ns = {"xs": "http://www.w3.org/2001/XMLSchema"}
        schema = ET.parse(SDK / "bin/resources.xsd").getroot()
        texture_xml = ET.parse(ROOT / "resources/textures/textures.xml").getroot()
        for element, type_name in ((texture_xml[0], "bitmapType"),):
            definition = schema.find(f"xs:complexType[@name='{type_name}']", ns)
            self.assertIsNotNone(definition)
            attributes = {a.attrib["name"]: a.attrib["type"]
                          for a in definition.findall("xs:attribute", ns)}
            self.assertTrue(set(element.attrib) <= set(attributes))
            for name, value in element.attrib.items():
                if attributes[name] == "xs:boolean":
                    self.assertIn(value, ("true", "false"))
        for name, value in (("packingFormat", texture_xml[0].attrib["packingFormat"]),
                            ("dithering", texture_xml[0].attrib["dithering"])):
            values = {e.attrib["value"] for e in schema.findall(
                f"xs:simpleType[@name='{name}Enum']/xs:restriction/xs:enumeration", ns)}
            self.assertIn(value, values)
        device = (SDK / "doc/docs/Device_Reference/fr265.html").read_text(encoding="utf-8")
        plain = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", device)))
        self.assertRegex(plain, r"Watch Face\s+131072\b")
        self.assertRegex(plain, r"Screen Size\s+416 x 416\b")
        self.assertRegex(plain, r"Display Colors\s+65536\b")

    def test_all_api_method_references_and_argument_counts(self):
        # This is a name/arity audit, not type inference or device compilation.
        # Fail closed on unfamiliar receivers so additions need explicit review.
        receivers = {
            "dc": ["Graphics.Dc"], "AppBase": ["Application.AppBase"],
            "WatchFace": ["WatchUi.WatchFace"],
            "_solarEvents": ["Lang.Array"], "_solarKinds": ["Lang.Array"],
            "points": ["Lang.Array"],
            "bandX": ["Lang.Array"], "bandY": ["Lang.Array"],
            "_location": ["Position.Location"],
            "history": ["SensorHistory.SensorHistoryIterator"],
            "forecasts": ["Lang.Array"],
            "best": ["Time.Moment"], "candidate": ["Time.Moment"],
            "now": ["Time.Moment"], "today": ["Time.Moment"],
            "sample.when": ["Time.Moment"], "wx.observationTime": ["Time.Moment"],
            "data.solarLabel": ["Lang.String"],
            "data.solarTime": ["Lang.String"],
            "kind": ["Lang.String"], "frameKey": ["Lang.String"],
            "data.battery": ["Lang.Number"], "data.heartRate": ["Lang.Number"],
            "data.humidity": ["Lang.Number"], "data.bodyBattery": ["Lang.Number"],
            "id": ["Complications.Id"],
            "h": ["Lang.Number"], "hour": ["Lang.Number"], "minute": ["Lang.Number"],
            "n": ["Lang.Number"], "info.day": ["Lang.Number"],
            "value": ["Lang.Number", "Lang.Float"],
            "sample.data": ["Lang.Number", "Lang.Float"],
        }
        numeric = ["Lang.Number", "Lang.Float", "Lang.Long", "Lang.Double"]
        chains = {"toNumber": numeric, "toFloat": numeric, "format": numeric,
                  "add": ["Time.Moment"], "value": ["Time.Moment"]}
        local_classes = {"view.data": "PrismelierData.mc", "data": "PrismelierData.mc", "view": "PrismelierView.mc",
                         "PrismelierPalette": "PrismelierPalette.mc"}
        cache = {}
        checked = set()
        constants_checked = set()

        def assert_documented(owner, method, argc):
            if (owner, method) == ("Application.AppBase", "initialize"):
                # This constructor has no method anchor in API docs, but the
                # official SDK Analog watch-face sample invokes it verbatim.
                sample = SDK / "samples/Analog/source/AnalogApp.mc"
                self.assertTrue(sample.is_file(), str(sample))
                self.assertIn("AppBase.initialize();", sample.read_text(encoding="utf-8"))
                self.assertEqual(argc, 0)
                checked.add((owner, method))
                return
            if owner not in cache:
                path = SDK / "doc/Toybox" / (owner.replace(".", "/") + ".html")
                self.assertTrue(path.is_file(), str(path))
                cache[owner] = path.read_text(encoding="utf-8")
            document = cache[owner]
            anchor = method + "-instance_function"
            match = re.search(r'<h3\b[^>]*\bid="' + re.escape(anchor) + r'"[^>]*>(.*?)</h3>',
                              document, re.S)
            self.assertIsNotNone(match, f"Undocumented SDK method {owner}.{method}")
            signature = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
            # Generic argument types may themselves contain comma-separated
            # tuples. Erase balanced <...> before counting signature parameters.
            while re.search(r"<[^<>]*>", signature):
                signature = re.sub(r"<[^<>]*>", "TYPE", signature)
            expected = argument_count(signature, signature.index("("))
            self.assertEqual(argc, expected, f"Argument count for {owner}.{method}: {signature.strip()}")
            checked.add((owner, method))

        for path in sorted(SOURCE.glob("*.mc")):
            code = without_comments(path.read_text(encoding="utf-8"))
            imports = {}
            for full, alias in re.findall(r"using\s+Toybox\.([\w.]+)(?:\s+as\s+(\w+))?\s*;", code):
                imports[alias or full.split(".")[-1]] = full
            for module, constant in re.findall(r"\b([A-Z][A-Za-z]+)\.([A-Z][A-Z0-9_]+)\b", code):
                if module not in imports:
                    continue
                owner = imports[module]
                document_path = SDK / "doc/Toybox" / (owner.replace(".", "/") + ".html")
                self.assertTrue(document_path.is_file(), str(document_path))
                document = document_path.read_text(encoding="utf-8")
                self.assertIn('id="' + constant + '-const"', document,
                              f"Undocumented SDK constant {owner}.{constant}")
                constants_checked.add((owner, constant))
            for match in re.finditer(r"\b([A-Za-z_]\w*(?:\.\w+)*)\.([A-Za-z_]\w*)\s*\(", code):
                receiver, method = match.groups()
                argc = argument_count(code, match.end() - 1)
                if receiver in local_classes:
                    local = source_text(local_classes[receiver])
                    definition = re.search(r"\bfunction\s+" + re.escape(method) + r"\s*\(", local)
                    self.assertIsNotNone(definition, receiver + "." + method)
                    self.assertEqual(argc, argument_count(local, definition.end() - 1))
                    continue
                root, *suffix = receiver.split(".")
                if root in imports:
                    owner = ".".join([imports[root]] + suffix)
                    if method[0].isupper():
                        # new Time.Duration(...) resolves to Duration.initialize.
                        owner += "." + method
                        method = "initialize"
                    owners = [owner]
                else:
                    self.assertIn(receiver, receivers, "Unreviewed API receiver: " + receiver)
                    owners = receivers[receiver]
                for owner in owners:
                    assert_documented(owner, method, argc)
            for match in re.finditer(r"\)\.([A-Za-z_]\w*)\s*\(", code):
                method = match.group(1)
                self.assertIn(method, chains, "Unreviewed chained API method: " + method)
                argc = argument_count(code, match.end() - 1)
                for owner in chains[method]:
                    assert_documented(owner, method, argc)
        self.assertIn(("Lang.String", "find"), checked)
        self.assertNotIn(("Math", "min"), checked)
        self.assertNotIn(("Math", "max"), checked)
        print(f"\nOfficial SDK method audit: {len(checked)} owner/method pairs verified; "
              f"{len(constants_checked)} module constants verified; method IDs/arity checked, "
              "AppBase constructor backed by official sample")

    def test_weather_constants_exist_in_official_sdk_docs(self):
        path = SDK / "doc/Toybox/Weather.html"
        self.assertTrue(path.is_file(), str(path))
        documented = set(re.findall(r"CONDITION_[A-Z_]+", path.read_text(encoding="utf-8")))
        referenced = set(re.findall(r"Weather\.(CONDITION_[A-Z_]+)", source_text("PrismelierData.mc")))
        self.assertTrue(referenced)
        self.assertEqual(referenced - documented, set())

    def test_humidity_documented_units(self):
        document = (SDK / "doc/Toybox/Weather/CurrentConditions.html").read_text(encoding="utf-8")
        self.assertIn("relativeHumidity", document)
        self.assertIn("0-100%", document)


    def test_official_monkeydoc_parser_no_diagnostics(self):
        if shutil.which("java") is None:
            self.skipTest("Java not installed; official parser check skipped")
        parser = SDK / "bin/monkeydoc"
        api = SDK / "bin/api.mir"
        self.assertTrue(parser.is_file(), str(parser))
        self.assertTrue(api.is_file(), str(api))
        files = sorted(SOURCE.glob("*.mc"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        with tempfile.TemporaryDirectory(prefix="prismelier-parser-") as temp:
            result = subprocess.run([str(parser), "-f", str(api), "-o", temp, *map(str, files)],
                                    text=True, capture_output=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            # monkeydoc can print parser errors while returning zero.
            self.assertEqual((result.stdout + result.stderr).strip(), "",
                             "Unexpected parser diagnostics; inspect, do not trust exit code alone")
            for path in files:
                names = re.findall(r"\b(?:class|module)\s+(\w+)", without_comments(path.read_text()))
                self.assertTrue(names, str(path))
                for name in names:
                    self.assertTrue((Path(temp) / "Global" / (name + ".html")).is_file(), name)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files},
                         "Source changed during parser verification; rerun against final sources")


if __name__ == "__main__":
    unittest.main(verbosity=2)
