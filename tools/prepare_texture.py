#!/usr/bin/env python3
"""Deterministically downsize/pack a chosen texture; never generates or edits art.
The build uses the committed 416px asset and does not need this script.
"""
from pathlib import Path
import argparse
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('input',type=Path,help='The selected source background image')
p.add_argument('--output',type=Path,default=ROOT/'resources/textures/foundry-background-indexed.png')
a=p.parse_args()
art=Image.open(a.input).convert('RGB').resize((384,384),Image.Resampling.LANCZOS)
im=Image.new('RGB',(416,416),'black')
im.paste(art,(16,16)) # Deliberate inset for the round display's safe area
im=im.quantize(colors=256,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
a.output.parent.mkdir(parents=True,exist_ok=True)
im.save(a.output,optimize=True)
print(f'{a.output}: {a.output.stat().st_size} bytes, {im.width}x{im.height}, opaque indexed PNG')
