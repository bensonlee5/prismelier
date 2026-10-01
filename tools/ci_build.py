#!/usr/bin/env python3
"""Real FR265 CI build on an officially provisioned Linux runner.

No downloads, key generation, login, SDK redistribution, or simulated success.
CIQ_SDK and CIQ_KEY are local runner environment variables, not GitHub secrets.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SDK_VERSION = '9.2.0'
# Official Linux SDK 9.2.0 download, independently checked 2026-10-01.
COMPILER_SHA256 = 'b9be696349c91feec3fb9723584daf624421d197f76ff86f72c7b3f66492fc9f'


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def profile_digest(folder):
    """Fingerprint inputs without publishing Garmin's profile contents."""
    h = hashlib.sha256()
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            h.update(path.relative_to(folder).as_posix().encode() + b'\0')
            h.update(bytes.fromhex(digest(path)))
    return h.hexdigest()


def preflight():
    if platform.system() != 'Linux':
        raise ValueError('This workflow requires the dedicated Linux runner; see docs/CI.md.')
    if sys.version_info < (3, 10):
        raise ValueError('Python 3.10 or newer is required.')
    for name in ('CIQ_SDK', 'CIQ_KEY'):
        if not os.environ.get(name):
            raise ValueError(f'{name} is missing from the local runner environment. See docs/CI.md.')
    sdk = Path(os.environ['CIQ_SDK']).expanduser().resolve()
    key = Path(os.environ['CIQ_KEY']).expanduser().resolve()
    if key.is_relative_to(ROOT):
        raise ValueError('The signing key must stay outside the repository.')
    if not key.is_file():
        raise ValueError('The local signing key is missing. Do not upload it to GitHub.')
    compiler = sdk / 'bin' / 'monkeyc'
    jar = sdk / 'bin' / 'monkeybrains.jar'
    if not compiler.is_file() or not jar.is_file():
        raise ValueError('Official Connect IQ SDK is missing. Install it using Garmin SDK Manager.')
    if digest(jar) != COMPILER_SHA256:
        raise ValueError('Compiler hash differs from pinned official SDK 9.2.0. Review before updating the pin.')
    version = subprocess.run([str(compiler), '-v'], check=True, text=True,
                             capture_output=True, timeout=30).stdout.strip()
    if version != f'Connect IQ Compiler version: {SDK_VERSION}':
        raise ValueError('Unexpected compiler version; this workflow pins SDK 9.2.0.')
    profile = Path.home() / '.Garmin' / 'ConnectIQ' / 'Devices' / 'fr265'
    if not (profile / 'compiler.json').is_file():
        raise ValueError('Official FR265 device profile is missing for this runner user. '
                         'Sign in to Garmin SDK Manager and install Forerunner 265. '
                         'The SDK ZIP alone is insufficient; see docs/CI.md.')
    # Validate the configuration is readable; the actual compiler validates its schema.
    json.loads((profile / 'compiler.json').read_text())
    print(f'Preflight passed: pinned compiler {SDK_VERSION}, provisioned FR265 profile and external local key present.')
    print('Preflight is not a compile or a simulator/hardware test.')
    return sdk, profile


def build():
    sdk, profile = preflight()
    profile_before = profile_digest(profile)
    # Never copy a private key into the checkout, logs, cache, or artifact directory.
    output = ROOT / 'build'
    if output.is_symlink():
        raise ValueError('Refusing a symlinked build directory.')
    output.mkdir(exist_ok=True)
    prg = output / 'Prismelier.prg'
    stage = output / 'ci-artifact'
    if stage.is_symlink():
        raise ValueError('Refusing a symlinked artifact directory.')
    # These are this helper's generated outputs, never source or developer keys.
    prg.unlink(missing_ok=True)
    if stage.exists():
        shutil.rmtree(stage)
    subprocess.run([sys.executable, str(ROOT / 'tools' / 'build.py'), '--release'],
                   cwd=ROOT, check=True)
    if prg.is_symlink() or not prg.is_file() or prg.stat().st_size == 0:
        raise ValueError('Compiler did not produce a new, nonempty Prismelier.prg.')
    if profile_digest(profile) != profile_before:
        raise ValueError('Device profile changed during compilation. Retry with stable installed inputs.')
    stage.mkdir()
    shutil.copyfile(prg, stage / prg.name)
    record = {
        'application': 'Prismelier',
        'device': 'fr265',
        'sdkVersion': SDK_VERSION,
        'compilerSha256': digest(sdk / 'bin' / 'monkeybrains.jar'),
        'deviceProfileSha256': profile_before,
        'sourceCommit': os.environ.get('GITHUB_SHA', 'local-unrecorded'),
        'runId': os.environ.get('GITHUB_RUN_ID'),
        'runAttempt': os.environ.get('GITHUB_RUN_ATTEMPT'),
        'programBytes': prg.stat().st_size,
        'programSha256': digest(prg),
        'releaseBuild': True,
        'typeCheckLevel': 1,
        'simulatorTested': False,
        'hardwareTested': False,
    }
    (stage / 'build-info.json').write_text(json.dumps(record, indent=2) + '\n')
    (stage / 'SHA256SUMS').write_text(
        f'{digest(prg)}  Prismelier.prg\n'
        f'{digest(stage / "build-info.json")}  build-info.json\n')
    print(f'Compiled FR265 artifact: {record["programBytes"]:,} bytes; SHA-256 {record["programSha256"]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('preflight', 'compile'))
    args = parser.parse_args()
    try:
        preflight() if args.command == 'preflight' else build()
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f'CI build failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
