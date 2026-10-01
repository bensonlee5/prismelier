#!/usr/bin/env python3
"""Build against the real Garmin FR265 profile. Never downloads SDKs or keys."""
from pathlib import Path
import argparse, os, platform, subprocess, sys
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--sdk', default=os.environ.get('CIQ_SDK'), help='Connect IQ SDK directory (or CIQ_SDK)')
p.add_argument('--key', default=os.environ.get('CIQ_KEY'), help='Private developer key DER path outside the repository (or CIQ_KEY)')
p.add_argument('--release', action='store_true', help='Strip debug information for USB sideloading')
p.add_argument('--test', action='store_true', help='Include Run No Evil tests')
a = p.parse_args()
if not a.sdk or not a.key:
    p.error('Pass --sdk and --key, or set CIQ_SDK and CIQ_KEY. See docs/INSTALL.md.')
sdk, key = Path(a.sdk).expanduser().resolve(), Path(a.key).expanduser().resolve()
if not key.is_file(): p.error('Developer key does not exist. Generate your own in the Garmin extension; never commit it.')
if key.is_relative_to(ROOT): p.error('Keep your developer key outside this public repository.')
compiler = sdk/'bin'/('monkeyc.bat' if platform.system() == 'Windows' else 'monkeyc')
if not compiler.is_file(): p.error(f'Compiler not found: {compiler}')
out=ROOT/'build'; out.mkdir(exist_ok=True)
cmd=[str(compiler), '-f', str(ROOT/'monkey.jungle'), '-d', 'fr265', '-o', str(out/'Prismelier.prg'), '-y', str(key), '-w', '-l', '1']
if a.release: cmd.append('-r')
if a.test: cmd.append('-t')
# Device profiles are installed by Garmin SDK Manager. Let the official compiler
# reject absent/invalid profiles rather than faking a compatible target.
result=subprocess.run(cmd, cwd=ROOT, shell=(platform.system() == 'Windows'))
if result.returncode: sys.exit(result.returncode)
print('Built:',out/'Prismelier.prg')
print('Target: Forerunner 265 ONLY. This compile is not a hardware test.')
