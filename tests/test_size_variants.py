"""Geometry/font/asset evidence only: never described as a native simulator test."""
import importlib.util
from functools import lru_cache
import math
import hashlib
import json
from pathlib import Path
import re
import shlex
import tempfile
import unittest
from test_project import clock_text

try:
    from PIL import Image, ImageChops, ImageFilter
except ImportError:
    Image = None

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('scale_layout', ROOT / 'tools/scale_layout.py')
layout = importlib.util.module_from_spec(spec)
spec.loader.exec_module(layout)


@lru_cache(maxsize=None)
def metadata(size, name):
    result = {'glyphs': {}}
    path = ROOT / f'packaging/variants/{size}/fonts/{name}.fnt'
    for line in path.read_text().splitlines():
        tokens = shlex.split(line)
        if tokens[0] in ('char', 'common'):
            values = {k: int(v) for k, v in (token.split('=', 1) for token in tokens[1:])}
            if tokens[0] == 'char':
                result['glyphs'][values['id']] = values
            else:
                result['common'] = values
    return result


def bounds(font, text, center, top):
    glyphs = font['glyphs']
    x = center - sum(glyphs[ord(c)]['xadvance'] for c in text) / 2
    boxes = []
    for c in text:
        g = glyphs[ord(c)]
        boxes.append((x + g['xoffset'], top + g['yoffset'],
                      x + g['xoffset'] + g['width'], top + g['yoffset'] + g['height']))
        x += g['xadvance']
    return boxes


class VariantGeometryTests(unittest.TestCase):
    def test_variants_match_current_master_asset_hashes(self):
        for size in layout.SIZES:
            info = json.loads((ROOT / f'packaging/variants/{size}/variant-info.json').read_text())
            self.assertEqual(info['size'], size)
            for name, expected in info['masterSha256'].items():
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), expected, name)

    def test_unknown_drawing_api_and_double_scaling_fail_closed(self):
        source = (ROOT / 'source/PrismelierView.mc').read_text()
        for size in layout.SIZES:
            adapted = layout.adapt_source(source, size)
            with self.assertRaisesRegex(ValueError, 'already adapted'):
                layout.adapt_source(adapted, size)
            with self.assertRaisesRegex(ValueError, 'new Dc methods'):
                layout.adapt_source(source + '\ndc.drawArc(1, 2, 3, 4, 5, 6);', size)

    def test_every_current_coordinate_call_is_scaled(self):
        source = (ROOT / 'source/PrismelierView.mc').read_text()
        for size in layout.SIZES:
            adapted = layout.adapt_source(source, size)
            self.assertIn(f'value * {size}.0 / 416.0', adapted)
            for method in layout.COORDINATES:
                calls = re.findall(rf'dc\.{method}\(([^;]*?)\);', adapted)
                self.assertEqual(len(calls), len(re.findall(rf'dc\.{method}\(', source)))
                for call in calls:
                    args = layout.split_arguments(call)
                    self.assertTrue(all(a.startswith('layoutPixel(') for a in args[:layout.COORDINATES[method]]))
            self.assertIn('dc.fillPolygon(layoutPolygon([[229, 273]', adapted)
            self.assertNotIn('BufferedBitmap', adapted.replace('// copy the image into a second full-screen BufferedBitmap.', ''))

    def inside(self, size, font, value, center, top, well):
        scale = size / 416
        for x0, y0, x1, y1 in bounds(metadata(size, font), value, center * scale, top * scale):
            self.assertGreaterEqual(x0, well[0] * scale, (size, value, 'left', x0))
            self.assertGreaterEqual(y0, well[1] * scale, (size, value, 'top', y0))
            self.assertLessEqual(x1, well[2] * scale, (size, value, 'right', x1))
            self.assertLessEqual(y1, well[3] * scale, (size, value, 'bottom', y1))

    def test_all_clock_strings_and_suffix_fit_scaled_visor(self):
        for size in layout.SIZES:
            for mode in (True, False):
                for minute in range(1440):
                    value = clock_text(minute, mode)
                    self.inside(size, 'Time', value, 208 if mode else 192, 77, (69, 90, 347, 171))
                    if not mode:
                        time_right = max(b[2] for b in bounds(metadata(size, 'Time'), value, 192 * size / 416, 77 * size / 416))
                        suffix_left = min(b[0] for b in bounds(metadata(size, 'Label'), 'AM', 324 * size / 416, 148 * size / 416))
                        self.assertLess(time_right + 1, suffix_left)
            self.inside(size, 'Label', 'AM', 324, 148, (69, 90, 347, 171))
            self.inside(size, 'Label', 'PM', 324, 148, (69, 90, 347, 171))

    def test_dates_labels_and_worst_metrics_fit_scaled_panels(self):
        data = (ROOT / 'source/PrismelierData.mc').read_text()
        labels = set(re.findall(r'weatherLabel = "([^"]+)"', data)) - {'AGED '}
        labels.update(f'AGED {h}H' for h in range(2, 24))
        for size in layout.SIZES:
            for month in 'Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split():
                for day in range(1, 32):
                    self.inside(size, 'Small', f'{month} {day}', 208, 176, (160, 177, 256, 205))
            for text in labels:
                self.inside(size, 'Label', text, 286, 242, (223, 242, 351, 271))
            for text in ('11:59 AM', '12:00 PM'):
                self.inside(size, 'Label', text, 307, 285, (267, 276, 348, 310))
            self.inside(size, 'Value', '220', 149, 339, (114, 342, 183, 379))
            for text in ('100,000', '999,999'):
                self.inside(size, 'Small', text, 284, 342, (237, 342, 337, 379))
            self.inside(size, 'Label', '1,000,000', 284, 346, (237, 342, 337, 379))

    def test_weekday_glyphs_stay_inside_round_screen(self):
        for size in layout.SIZES:
            scale = size / 416
            for i, letter in enumerate('SMTWTFS'):
                angle = math.radians(210 + i * 20)
                x, y = (208 + 188 * math.cos(angle)) * scale, (208 + 188 * math.sin(angle)) * scale
                for box in bounds(metadata(size, 'Small'), letter, x, y - 12 * scale):
                    for xx in (box[0], box[2]):
                        for yy in (box[1], box[3]):
                            self.assertLess(math.hypot(xx - size / 2, yy - size / 2), size / 2 - 1)


@unittest.skipUnless(Image is not None, 'Pillow unavailable; asset pixel checks skipped')
class VariantAssetTests(unittest.TestCase):
    def test_resource_dimensions_glyph_coverage_and_texture_circle(self):
        for size in layout.SIZES:
            root = ROOT / f'packaging/variants/{size}'
            texture = Image.open(root / 'textures/foundry-background-indexed.png')
            self.assertEqual(texture.size, (size, size))
            self.assertEqual(texture.mode, 'P')
            self.assertNotIn('transparency', texture.info)
            texture_rgb = texture.convert('RGB')
            for y in range(size):
                for x in range(size):
                    if max(texture_rgb.getpixel((x, y))) > 8:
                        self.assertLess(math.hypot(x - size / 2, y - size / 2), size / 2)
            for name in ('Time', 'Value', 'Small', 'Label', 'Ambient'):
                font = metadata(size, name)
                atlas = Image.open(root / f'fonts/{name}.png').copy()
                self.assertEqual(atlas.size, (font['common']['scaleW'], font['common']['scaleH']))
                for glyph in font['glyphs'].values():
                    self.assertGreaterEqual(glyph['x'], 0)
                    self.assertGreaterEqual(glyph['y'], 0)
                    self.assertLessEqual(glyph['x'] + glyph['width'], atlas.width)
                    self.assertLessEqual(glyph['y'] + glyph['height'], atlas.height)
                self.assertTrue(set(map(ord, '0123456789:')).issubset(font['glyphs']))

    def test_aod_all_times_under_ten_percent_and_bands_disjoint(self):
        for size in layout.SIZES:
            font = metadata(size, 'Ambient')
            atlas = Image.open(ROOT / f'packaging/variants/{size}/fonts/Ambient.png').convert('L')
            union = Image.new('L', (size, font['common']['lineHeight'] + 4))
            circle_pixels = sum((x + .5 - size / 2) ** 2 + (y + .5 - size / 2) ** 2 <= (size / 2) ** 2
                                for x in range(size) for y in range(size))
            peak = 0
            for mode in (True, False):
                for minute in range(1440):
                    value = clock_text(minute, mode)
                    mask = Image.new('L', union.size)
                    x = (size - sum(font['glyphs'][ord(c)]['xadvance'] for c in value)) // 2
                    for c in value:
                        g = font['glyphs'][ord(c)]
                        glyph = atlas.crop((g['x'], g['y'], g['x'] + g['width'], g['y'] + g['height']))
                        mask.paste(glyph, (x + g['xoffset'], 2 + g['yoffset']))
                        x += g['xadvance']
                    mask = mask.point(lambda p: 255 if p else 0).filter(ImageFilter.MaxFilter(3))
                    peak = max(peak, sum(mask.histogram()[1:]))
                    union = ImageChops.lighter(union, mask)
            self.assertLess(peak / circle_pixels, .10)
            bands = []
            for slot in range(3):
                screen = Image.new('L', (size, size))
                screen.paste(union, (0, math.floor((92 + slot * 86) * size / 416) - 2))
                self.assertEqual(sum(screen.histogram()[1:]), sum(union.histogram()[1:]))
                box = screen.getbbox()
                for x in (box[0], box[2] - 1):
                    for y in (box[1], box[3] - 1):
                        self.assertLessEqual((x + .5 - size / 2) ** 2 + (y + .5 - size / 2) ** 2, (size / 2) ** 2)
                bands.append(screen)
            for i in range(3):
                for j in range(i + 1, 3):
                    self.assertIsNone(ImageChops.multiply(bands[i], bands[j]).getbbox())
            print(f'{size}px AOD asset model: peak {peak} lit pixels ({peak / circle_pixels:.2%}); bands disjoint; not firmware validation')
