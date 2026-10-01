#!/usr/bin/env python3
"""Generate compact, reproducible BMFont atlases from system DejaVu fonts.
Only required for editing fonts; generated assets are committed.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import argparse

ROOT = Path(__file__).resolve().parents[1]

def build(name, filename, size, chars):
    font = ImageFont.truetype(str(filename), size)
    ascent, descent = font.getmetrics()
    atlas = Image.new('L', (512, 512), 0)
    draw = ImageDraw.Draw(atlas)
    x = y = 1
    row = 0
    lines = []
    # Normalized top-origin glyph bounds let all renderers share coordinates.
    for c in chars:
        b = font.getbbox(c)
        w, h = max(1, b[2]-b[0]), max(1, b[3]-b[1])
        if x+w+2 > 512:
            x, y, row = 1, y+row+2, 0
        draw.text((x-b[0], y-b[1]), c, font=font, fill=255)
        advance = round(font.getlength(c))
        lines.append(f'char id={ord(c)} x={x} y={y} width={w} height={h} xoffset={b[0]} yoffset={b[1]} xadvance={advance} page=0 chnl=15')
        x += w+2
        row = max(row,h)
    height = y+row+1
    atlas = atlas.crop((0,0,512,height))
    # Garmin's font reader expects intensity in the RGB channels, no alpha.
    atlas.convert('RGB').save(ROOT/f'resources/fonts/{name}.png')
    data = [f'info face="DejaVu" size={size} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 padding=0,0,0,0 spacing=1,1',
        f'common lineHeight={ascent+descent} base={ascent} scaleW=512 scaleH={height} pages=1 packed=0',
        f'page id=0 file="{name}.png"', f'chars count={len(lines)}',*lines,'kernings count=0']
    (ROOT/f'resources/fonts/{name}.fnt').write_text('\n'.join(data)+'\n')

if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--font-dir',default='/usr/share/fonts/truetype/dejavu')
    d=Path(parser.parse_args().font_dir)
    build('Time', d/'DejaVuSansCondensed.ttf', 91, '0123456789:')
    build('Value', d/'DejaVuSans.ttf', 28, '0123456789-.,%°CF:AP')
    build('Small', d/'DejaVuSans.ttf', 20, ' ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-:.,%°/*')
    build('Label', d/'DejaVuSans.ttf', 15, ' ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-:.,%°/*')
    build('Ambient', d/'DejaVuSans-ExtraLight.ttf', 52, '0123456789:')
