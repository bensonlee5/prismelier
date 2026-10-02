#!/usr/bin/env python3
"""Generate reviewed AMOLED size variants from the 416px master.

Offline source/asset adaptation, not a native compile or simulator result.
No full-screen runtime framebuffer and no runtime bitmap/font resizing.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import shutil

ROOT = Path(__file__).resolve().parents[1]
SIZES = (360, 390, 454)
# Coordinate-bearing Dc methods used by this renderer. Fail on unknown methods
# so new art cannot silently bypass device adaptation.
COORDINATES = {'drawText': 2, 'drawLine': 4, 'fillCircle': 3, 'drawCircle': 3,
               'drawEllipse': 4, 'fillRoundedRectangle': 5, 'drawRoundedRectangle': 5,
               'drawBitmap': 2}
PASSTHROUGH = {'setColor', 'clear', 'setAntiAlias'}


def split_arguments(text):
    args, start, depth = [], 0, 0
    for i, char in enumerate(text):
        if char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif char == ',' and depth == 0:
            args.append(text[start:i].strip())
            start = i + 1
    args.append(text[start:].strip())
    return args


def adapt_source(source, size):
    if size not in SIZES:
        raise ValueError('Only reviewed 360/390/454 round AMOLED layouts can be generated')
    if 'function layoutPixel(' in source:
        raise ValueError('Source is already adapted')
    if source.count('    function initialize() {') != 1:
        raise ValueError('Review adaptation insertion point for this source revision')
    methods = set(re.findall(r'\bdc\.(\w+)\(', source))
    unknown = methods - set(COORDINATES) - PASSTHROUGH - {'fillPolygon', 'setPenWidth'}
    if unknown:
        raise ValueError('Review coordinate handling for new Dc methods: ' + ', '.join(sorted(unknown)))
    def replace(match):
        method, arguments = match.groups()
        if method in PASSTHROUGH:
            return match.group(0)
        if method == 'fillPolygon':
            return f'dc.fillPolygon(layoutPolygon({arguments}));'
        if method == 'setPenWidth':
            return f'dc.setPenWidth(layoutPen({arguments}));'
        args = split_arguments(arguments)
        for index in range(COORDINATES[method]):
            args[index] = f'layoutPixel({args[index]})'
        return f'dc.{method}(' + ', '.join(args) + ');'
    source = re.sub(r'\bdc\.(\w+)\(([^;]*?)\);', replace, source)
    helpers = f'''    // Generated {size}px AMOLED geometry. Fonts and texture are pre-sized assets.
    // Keep decimal coordinates until Dc conversion, as on the original face.
    function layoutPixel(value) {{ return value * {size}.0 / 416.0; }}
    function layoutPen(value) {{
        var scaled = Math.round(layoutPixel(value)).toNumber();
        return scaled < 1 ? 1 : scaled;
    }}
    function layoutPolygon(points) {{
        // The call site owns this temporary polygon; scale it in place.
        for (var i = 0; i < points.size(); i += 1) {{
            points[i][0] = layoutPixel(points[i][0]);
            points[i][1] = layoutPixel(points[i][1]);
        }}
        return points;
    }}

'''
    return source.replace('    function initialize() {', helpers + '    function initialize() {', 1)


def rounded(value, ratio):
    return math.floor(value * ratio + 0.5)


def scale_font(source, destination, name, size):
    from PIL import Image
    ratio = size / 416
    lines = (source / f'{name}.fnt').read_text().splitlines()
    original = Image.open(source / f'{name}.png').convert('RGB')
    atlas = Image.new('RGB', (512, 512), 0)
    x = y = 1
    row = 0
    output = []
    for line in lines:
        tokens = shlex.split(line)
        kind = tokens[0]
        values = dict(t.split('=', 1) for t in tokens[1:])
        if kind == 'char':
            g = {k: int(v) for k, v in values.items()}
            width, height = max(1, rounded(g['width'], ratio)), max(1, rounded(g['height'], ratio))
            if x + width + 2 > 512:
                x, y, row = 1, y + row + 2, 0
            glyph = original.crop((g['x'], g['y'], g['x'] + g['width'], g['y'] + g['height']))
            atlas.paste(glyph.resize((width, height), Image.Resampling.LANCZOS), (x, y))
            g.update(x=x, y=y, width=width, height=height)
            for key in ('xoffset', 'yoffset', 'xadvance'):
                g[key] = rounded(g[key], ratio)
            output.append('char ' + ' '.join(f'{k}={v}' for k, v in g.items()))
            x += width + 2
            row = max(row, height)
        elif kind == 'common':
            for key in ('lineHeight', 'base'):
                values[key] = rounded(int(values[key]), ratio)
            output.append('common ' + ' '.join(f'{k}={v}' for k, v in values.items()))
        elif kind == 'info':
            output.append(re.sub(r'size=\d+', lambda m: 'size=' + str(rounded(int(m[0][5:]), ratio)), line))
        else:
            output.append(line)
    height = y + row + 1
    output = [re.sub(r'scaleH=\d+', f'scaleH={height}', line) if line.startswith('common ') else line for line in output]
    atlas.crop((0, 0, 512, height)).save(destination / f'{name}.png')
    (destination / f'{name}.fnt').write_text('\n'.join(output) + '\n')


def generate(size, destination):
    from PIL import Image
    fonts = destination / 'fonts'
    textures = destination / 'textures'
    fonts.mkdir(parents=True, exist_ok=True)
    textures.mkdir(parents=True, exist_ok=True)
    for name in ('Time', 'Value', 'Small', 'Label', 'Ambient'):
        scale_font(ROOT / 'resources/fonts', fonts, name, size)
    for name in ('fonts.xml', 'LICENSE-DejaVu.txt'):
        shutil.copyfile(ROOT / 'resources/fonts' / name, fonts / name)
    texture = Image.open(ROOT / 'resources/textures/foundry-background-indexed.png').convert('RGB')
    texture = texture.resize((size, size), Image.Resampling.LANCZOS)
    texture.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(
        textures / 'foundry-background-indexed.png')
    shutil.copyfile(ROOT / 'resources/textures/textures.xml', textures / 'textures.xml')
    masters = [p for folder in ('fonts', 'textures') for p in sorted((ROOT / 'resources' / folder).iterdir()) if p.is_file()]
    (destination / 'variant-info.json').write_text(json.dumps({
        'size': size, 'masterSize': 416, 'masterSha256': {
            p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in masters}
    }, indent=2) + '\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    for size in SIZES:
        generate(size, ROOT / f'packaging/variants/{size}')
