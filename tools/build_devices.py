#!/usr/bin/env python3
"""Compile isolated per-device packages from a Git ref using a locally provisioned SDK.

No SDK/profile downloads, key generation, or signing-key uploads. A successful
compile is NOT simulator or hardware validation. See docs/MULTI_DEVICE.md.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

# Also importable by offline tests without altering sys.path globally.
import importlib.util
_adapter_spec = importlib.util.spec_from_file_location(
    "scale_layout", Path(__file__).with_name("scale_layout.py"))
_adapter = importlib.util.module_from_spec(_adapter_spec)
_adapter_spec.loader.exec_module(_adapter)

ROOT = Path(__file__).resolve().parents[1]
NS = 'http://www.garmin.com/xml/connectiq'
SDK_VERSION = '9.2.0'


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fingerprint(folder):
    h = hashlib.sha256()
    for path in sorted(folder.rglob('*')):
        if path.is_file():
            h.update(path.relative_to(folder).as_posix().encode() + b'\0')
            h.update(bytes.fromhex(sha256(path)))
    return h.hexdigest()


def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])


def resolve_ref(ref):
    return git('rev-parse', '--verify', '--end-of-options', ref + '^{commit}').decode().strip()


def snapshot(commit, destination, variant=None):
    """Only tracked build inputs; exclude old dist binaries and arbitrary scripts."""
    paths = ['manifest.xml', 'monkey.jungle', 'source', 'resources']
    if variant is not None:
        paths.append(f'packaging/variants/{variant}')
    archive = git('archive', commit, *paths)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for item in tar:
            target = destination / item.name
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError('Unsafe archive path')
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            elif item.isfile():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(item).read())
            else:
                raise ValueError('Build inputs must not contain symlinks or special files')


def prepare_source(commit, source, device):
    size = device['width']
    if size != device['height'] or device['shape'] != 'round' or device['display'] != 'AMOLED':
        raise ValueError('No layout/resource implementation for this display')
    if size not in (360, 390, 416, 454):
        raise ValueError('No reviewed source adaptation for this resolution')
    snapshot(commit, source, size if size != 416 else None)
    if size != 416:
        variant = source / f'packaging/variants/{size}'
        provenance = json.loads((variant / 'variant-info.json').read_text())
        for name, expected in provenance['masterSha256'].items():
            if sha256(source / name) != expected:
                raise ValueError('Scaled assets are stale relative to this ref; regenerate with tools/scale_layout.py')
        for folder in ('fonts', 'textures'):
            shutil.rmtree(source / 'resources' / folder)
            shutil.copytree(variant / folder, source / 'resources' / folder)
        shutil.rmtree(source / 'packaging')
        view = source / 'source/PrismelierView.mc'
        view.write_text(_adapter.adapt_source(view.read_text(), size))
    return target_manifest(source, device['id'])


def target_manifest(source, device):
    tree = ET.parse(source / 'manifest.xml')
    application = tree.getroot().find(f'{{{NS}}}application')
    products = application.find(f'{{{NS}}}products')
    products.clear()
    ET.SubElement(products, f'{{{NS}}}product', {'id': device})
    ET.register_namespace('iq', NS)
    tree.write(source / 'manifest.xml', encoding='utf-8', xml_declaration=True)
    return application.attrib['id']


def verify_program(path, app_id):
    # Sanity check the real PRG container seen in Garmin SDK 9.2.0 output.
    # Target binding is established by isolated official monkeyc -d invocation,
    # a one-product manifest and fingerprinted device inputs, NOT by the filename.
    if path.is_symlink() or not path.is_file():
        raise ValueError('Compiler did not produce a regular PRG')
    data = path.read_bytes()
    if len(data) < 96 or data[:4] != bytes.fromhex('d000d00d'):
        raise ValueError('Output is not a Garmin PRG container')
    if bytes.fromhex(app_id) not in data[:512]:
        raise ValueError('PRG application ID does not match the source manifest')


def preflight(sdk_arg, key_arg):
    if not sdk_arg or not key_arg:
        raise ValueError('Set CIQ_SDK and CIQ_KEY (existing private key outside checkout), or pass --sdk/--key')
    sdk, key = Path(sdk_arg).expanduser().resolve(), Path(key_arg).expanduser().resolve()
    if key.is_relative_to(ROOT) or not key.is_file():
        raise ValueError('Existing signing key must be a file outside the repository')
    if platform.system() == 'Windows':
        raise ValueError('Use Linux/macOS for this packaging script; Windows single-device builds use tools/build.py')
    compiler = sdk / 'bin' / 'monkeyc'
    if not compiler.is_file() or not (sdk / 'bin' / 'monkeybrains.jar').is_file():
        raise ValueError('Official SDK compiler is absent; provision SDK 9.2.0 using Garmin SDK Manager')
    version = subprocess.check_output([str(compiler), '-v'], text=True, timeout=30).strip()
    if version != f'Connect IQ Compiler version: {SDK_VERSION}':
        raise ValueError('Expected official SDK 9.2.0; review compatibility before changing version')
    if platform.system() == 'Darwin':
        profiles = Path.home() / 'Library/Application Support/Garmin/ConnectIQ/Devices'
    else:
        profiles = Path.home() / '.Garmin/ConnectIQ/Devices'
    return sdk, key, profiles


def build_one(device, commit, sdk, key, profiles, output):
    target = device['id']
    profile = profiles / target
    if not (profile / 'compiler.json').is_file():
        raise ValueError(f'Official {target} profile absent; install it with Garmin SDK Manager for this OS user')
    json.loads((profile / 'compiler.json').read_text())
    before = fingerprint(profile)
    with tempfile.TemporaryDirectory(prefix=f'prismelier-{target}-') as temporary:
        stage = Path(temporary)
        source = stage / 'source-inputs'
        source.mkdir()
        app_id = prepare_source(commit, source, device)
        input_hash = fingerprint(source)
        prg = stage / f'Prismelier-{target}.prg'
        command = [str(sdk / 'bin/monkeyc'), '-f', str(source / 'monkey.jungle'),
                   '-d', target, '-o', str(prg), '-y', str(key), '-w', '-l', '1', '-r']
        # No raw compiler output is published: it can contain local paths.
        result = subprocess.run(command, cwd=source, capture_output=True, text=True, timeout=300)
        if result.returncode:
            print(result.stdout + result.stderr, file=sys.stderr)
            raise ValueError(f'Official compiler failed for {target} (exit {result.returncode}); see local diagnostic output')
        verify_program(prg, app_id)
        if fingerprint(profile) != before:
            raise ValueError('Device profile changed while compiling')
        package = output / target
        package.mkdir()
        shutil.copyfile(prg, package / prg.name)
        record = dict(application='Prismelier', device=target, deviceName=device['name'],
                      applicationId=app_id, sourceCommit=commit, sdkVersion=SDK_VERSION,
                      compilerSha256=sha256(sdk / 'bin/monkeybrains.jar'),
                      deviceProfileSha256=before, buildInputsSha256=input_hash,
                      layout=f'round-{device["width"]}-amoled',
                      layoutAdapterSha256=sha256(Path(__file__).with_name('scale_layout.py')), program=prg.name, programBytes=prg.stat().st_size,
                      programSha256=sha256(prg), releaseBuild=True, typeCheckLevel=1,
                      simulatorTested=False, hardwareTested=False,
                      validation='compiled-only; not approved for public release')
        write_json(package / 'build-info.json', record)
        (package / 'INSTALL.txt').write_text(
            f'Prismelier for {device["name"]} ({target}) ONLY\nSource: {commit}\n\n'
            'This is a compiled candidate. Simulator and hardware validation are separate.\n'
            'Do not install a package for a similar model or a different case size.\n'
            'Unzip, verify SHA256SUMS, then copy only the .prg file to the existing\n'
            'GARMIN/APPS folder over USB (MTP on some devices). Eject safely, disconnect,\n'
            'and select Prismelier in the watch face menu. Connect IQ on iPhone cannot\n'
            'import raw .prg files. Keep a backup; remove the face to uninstall.\n'
            'Use the same developer signing key for future builds to preserve continuity.\n'
            'Guide: https://github.com/bensonlee5/prismelier/blob/main/docs/INSTALL.md\n')
        (package / 'SHA256SUMS').write_text(''.join(
            f'{sha256(p)}  {p.name}\n' for p in sorted(package.iterdir())))
        return record


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def prepare(args):
    matrix = json.loads((ROOT / 'packaging/devices.json').read_text())
    devices = {d['id']: d for d in matrix['devices']}
    if args.device not in devices:
        raise ValueError('Unknown device ID')
    commit = resolve_ref(args.ref)
    output = Path(args.output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; choose a new path')
    source = output / 'project'
    source.mkdir(parents=True)
    prepare_source(commit, source, devices[args.device])
    write_json(output / 'prepared-info.json', {
        'sourceCommit': commit, 'device': args.device,
        'layoutPixels': devices[args.device]['width'], 'buildInputsSha256': fingerprint(source),
        'layoutAdapterSha256': sha256(Path(__file__).with_name('scale_layout.py')),
        'compiled': False, 'simulatorTested': False})
    print(f'Prepared {args.device} source/resources at {source}; NOT a compiled program')
    return 0


def build(args):
    commit = resolve_ref(args.ref)
    matrix = json.loads((ROOT / 'packaging/devices.json').read_text())
    by_id = {d['id']: d for d in matrix['devices']}
    targets = args.devices.split(',') if args.devices else [d['id'] for d in matrix['devices'] if d['phaseOne']]
    if len(set(targets)) != len(targets) or any(d not in by_id for d in targets):
        raise ValueError('Unknown or duplicate device; use only IDs in packaging/devices.json')
    sdk, key, profiles = preflight(args.sdk, args.key)
    # Refuse to reuse a previous run, including its successful or stale packages.
    output = Path(args.output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; choose a new empty output path')
    output.mkdir(parents=True)
    report = {'sourceCommit': commit, 'packagerSha256': sha256(Path(__file__)),
              'matrixSha256': sha256(ROOT / 'packaging/devices.json'), 'devices': []}
    for target in targets:
        try:
            record = build_one(by_id[target], commit, sdk, key, profiles, output)
            report['devices'].append({'device': target, 'status': 'compiled', 'programSha256': record['programSha256']})
            print(f'{target}: compiled; simulator validation required')
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            report['devices'].append({'device': target, 'status': 'failed', 'reason': str(exc)})
            print(f'{target}: FAILED: {exc}', file=sys.stderr)
        write_json(output / 'matrix-results.json', report)
    return 1 if any(d['status'] == 'failed' for d in report['devices']) else 0


def approved_packages(output, evidence):
    """Prepare ZIPs only for exact PRG hashes with recorded simulator review."""
    report = json.loads((output / 'matrix-results.json').read_text())
    approved = json.loads(evidence.read_text())
    if approved['sourceCommit'] != report['sourceCommit']:
        raise ValueError('Validation evidence source commit differs')
    packages = []
    for device, review in approved['devices'].items():
        if not re.fullmatch('[a-z0-9]+', device):
            raise ValueError('Invalid device ID')
        if not any(d['device'] == device and d['status'] == 'compiled' for d in report['devices']):
            raise ValueError(f'{device}: no successful compile in this run')
        folder = output / device
        record = json.loads((folder / 'build-info.json').read_text())
        prg = folder / f'Prismelier-{device}.prg'
        verify_program(prg, record['applicationId'])
        if (record['sourceCommit'] != report['sourceCommit'] or record['device'] != device or
                sha256(prg) != record['programSha256'] or sha256(prg) != review['programSha256']):
            raise ValueError(f'{device}: validation does not match this program')
        checks = ('correctDevice', 'allThemes', 'timeAndUnits', 'missingData', 'aodAndWake', 'memoryChecked')
        if not all(review.get(c) is True for c in checks) or not review.get('notes'):
            raise ValueError(f'{device}: incomplete simulator/graphics/memory review')
        packages.append((device, folder, record, review))
    if not packages:
        raise ValueError('No simulator-approved packages')
    return report, packages


def publish(args):
    output = Path(args.output).resolve()
    report, packages = approved_packages(output, Path(args.evidence))
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.tag):
        raise ValueError('Use an alphanumeric release tag with dots, underscores or hyphens')
    # Existing tags must point to the source commit. Never overwrite a release.
    remote = git('ls-remote', 'origin', f'refs/tags/{args.tag}', f'refs/tags/{args.tag}^{{}}').decode().splitlines()
    if remote:
        tag_commit = remote[-1].split()[0]
        if tag_commit != report['sourceCommit']:
            raise ValueError('Release tag already points at a different commit')
    release = output / 'release'
    release.mkdir()  # refuse stale publication assets
    for device, folder, record, review in packages:
        # Publish a fresh allowlisted archive; no logs, SDK or signing key.
        record.update(simulatorTested=True, hardwareTested=review.get('hardwareTested') is True,
                      validation=review)
        payload = {f'Prismelier-{device}.prg': (folder / f'Prismelier-{device}.prg').read_bytes(),
                   'build-info.json': (json.dumps(record, indent=2) + '\n').encode(),
                   'INSTALL.txt': (folder / 'INSTALL.txt').read_bytes().replace(
                       b'This is a compiled candidate. Simulator and hardware validation are separate.',
                       b'This build passed recorded simulator review. See build-info.json for hardware status.')}
        payload['SHA256SUMS'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                       for name, data in sorted(payload.items())).encode()
        with zipfile.ZipFile(release / f'Prismelier-{device}-{args.tag}.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, data in payload.items():
                archive.writestr(name, data)
    write_json(release / 'device-manifest.json', {
        'sourceCommit': report['sourceCommit'], 'version': args.tag,
        'devices': [record for _, _, record, _ in packages]})
    assets = sorted(release.iterdir())
    sums = release / 'SHA256SUMS'
    sums.write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in assets))
    assets.append(sums)
    notes = output / 'release-notes.md'
    notes.write_text(f'Prismelier {args.tag}\n\nSource: `{report["sourceCommit"]}`\n\n'
                     'Download the ZIP for your exact watch model. Unzip and follow INSTALL.txt. '
                     'SHA256SUMS and device-manifest.json record each build.\n\n'
                     + '\n'.join(f'- {r["deviceName"]} (`{d}`): simulator reviewed; hardware tested: {r["hardwareTested"]}'
                                 for d, _, r, _ in packages) + '\n\n'
                     'Other models are unsupported by this release. This is a sideload preview, not a Connect IQ Store listing.\n')
    subprocess.run(['gh', 'release', 'create', args.tag, '--repo', 'bensonlee5/prismelier',
                    '--target', report['sourceCommit'], '--title', f'Prismelier {args.tag}',
                    '--notes-file', str(notes), '--prerelease', '--draft', *map(str, assets)], check=True)
    # Upload completes before the draft becomes publicly downloadable.
    subprocess.run(['gh', 'release', 'edit', args.tag, '--repo', 'bensonlee5/prismelier', '--draft=false'], check=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    b = commands.add_parser('build')
    b.add_argument('--ref', required=True, help='Git ref resolved to immutable commit; working-tree edits excluded')
    b.add_argument('--devices', help='Comma-separated matrix IDs; default: ten phase-one candidates')
    b.add_argument('--sdk', default=os.environ.get('CIQ_SDK'))
    b.add_argument('--key', default=os.environ.get('CIQ_KEY'))
    b.add_argument('--output', required=True, help='New output directory; never overwrites')
    prep = commands.add_parser('prepare', help='Inspect generated source/resources without SDK or signing key')
    prep.add_argument('--ref', required=True)
    prep.add_argument('--device', required=True)
    prep.add_argument('--output', required=True)
    p = commands.add_parser('publish')
    p.add_argument('--output', required=True)
    p.add_argument('--evidence', required=True, help='Simulator checklist tied to exact program hashes')
    p.add_argument('--tag', required=True)
    args = parser.parse_args()
    try:
        return {'build': build, 'prepare': prepare, 'publish': publish}[args.command](args)
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f'Packaging failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
