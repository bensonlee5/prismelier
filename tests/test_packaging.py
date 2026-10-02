"""Offline packaging failure/identity checks; these fixtures are NOT Garmin builds."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('build_devices', ROOT / 'tools/build_devices.py')
pkg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pkg)


class PackagingTests(unittest.TestCase):
    def test_no_provisioning_fails_without_creating_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'out'
            args = SimpleNamespace(ref='HEAD', devices='fr265', sdk=None, key=None, output=str(output))
            with self.assertRaisesRegex(ValueError, 'CIQ_SDK'):
                pkg.build(args)
            self.assertFalse(output.exists())

    def test_unknown_model_never_invokes_compiler(self):
        args = SimpleNamespace(ref='HEAD', devices='fenix851mm')
        with patch.object(pkg, 'preflight') as preflight:
            with self.assertRaisesRegex(ValueError, 'Unknown'):
                pkg.build(args)
            preflight.assert_not_called()

    def test_key_must_stay_outside_repo(self):
        with self.assertRaisesRegex(ValueError, 'outside'):
            pkg.preflight('/no-sdk', str(ROOT / 'developer.der'))

    def test_snapshot_does_not_import_existing_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            pkg.snapshot(pkg.resolve_ref('HEAD'), out)
            self.assertTrue((out / 'source/PrismelierView.mc').is_file())
            self.assertFalse((out / 'dist').exists())
            app_id = pkg.target_manifest(out, 'epix2')
            self.assertEqual(app_id, '81c2a924768f4b9eb6ac52e438d0517f')
            tree = pkg.ET.parse(out / 'manifest.xml')
            products = tree.findall(f'.//{{{pkg.NS}}}product')
            self.assertEqual([p.attrib['id'] for p in products], ['epix2'])

    def test_container_validation_rejects_placeholder_and_wrong_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            prg = Path(tmp) / 'bad.prg'
            prg.write_bytes(b'not a program' * 100)
            with self.assertRaisesRegex(ValueError, 'container'):
                pkg.verify_program(prg, '00' * 16)
            prg.write_bytes(bytes.fromhex('d000d00d') + b'x' * 200)
            with self.assertRaisesRegex(ValueError, 'application ID'):
                pkg.verify_program(prg, '00' * 16)

    def test_real_historical_fr265_container_and_hash(self):
        prg = ROOT / 'dist/Prismelier-fr265.prg'
        pkg.verify_program(prg, '81c2a924768f4b9eb6ac52e438d0517f')
        record = json.loads((ROOT / 'dist/build-info.json').read_text())
        self.assertEqual(pkg.sha256(prg), record['programSha256'])

    def test_failure_is_per_target_nonzero_and_does_not_hide_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / 'run'
            args = SimpleNamespace(ref='HEAD', devices='fr265,epix2', sdk='sdk', key='key', output=str(out))
            with patch.object(pkg, 'preflight', return_value=('sdk', 'key', 'profiles')), \
                 patch.object(pkg, 'build_one', side_effect=[ValueError('missing profile'), {'programSha256':'test-only'}]):
                self.assertEqual(pkg.build(args), 1)
            report = json.loads((out / 'matrix-results.json').read_text())
            self.assertEqual([d['status'] for d in report['devices']], ['failed', 'compiled'])
            self.assertEqual(report['devices'][0]['reason'], 'missing profile')
            with patch.object(pkg, 'preflight', return_value=('sdk', 'key', 'profiles')):
                with self.assertRaisesRegex(ValueError, 'already exists'):
                    pkg.build(args)

    def evidence_fixture(self, root):
        # A real historical program is used for identity checks only; never released.
        folder = root / 'fr265'
        folder.mkdir()
        prg = folder / 'Prismelier-fr265.prg'
        prg.write_bytes((ROOT / 'dist/Prismelier-fr265.prg').read_bytes())
        record = {'sourceCommit': 'test-commit', 'device': 'fr265',
                  'applicationId': '81c2a924768f4b9eb6ac52e438d0517f', 'programSha256': pkg.sha256(prg)}
        pkg.write_json(folder / 'build-info.json', record)
        pkg.write_json(root / 'matrix-results.json', {'sourceCommit':'test-commit',
                       'devices':[{'device':'fr265', 'status':'compiled'}]})
        review = dict(programSha256=pkg.sha256(prg), notes='unit-test fixture; not real review',
                      correctDevice=True, allThemes=True, timeAndUnits=True, missingData=True,
                      aodAndWake=True, memoryChecked=True)
        evidence = root / 'evidence.json'
        pkg.write_json(evidence, {'sourceCommit':'test-commit', 'devices':{'fr265':review}})
        return evidence, review, prg

    def test_release_requires_exact_hash_and_complete_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, review, prg = self.evidence_fixture(root)
            _, packages = pkg.approved_packages(root, evidence)
            self.assertEqual(len(packages), 1)
            review['memoryChecked'] = False
            pkg.write_json(evidence, {'sourceCommit':'test-commit', 'devices':{'fr265':review}})
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                pkg.approved_packages(root, evidence)
            review['memoryChecked'] = True
            review['programSha256'] = 'different-program'
            pkg.write_json(evidence, {'sourceCommit':'test-commit', 'devices':{'fr265':review}})
            with self.assertRaisesRegex(ValueError, 'does not match'):
                pkg.approved_packages(root, evidence)

    def test_release_rejects_failed_device_and_source_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, review, _ = self.evidence_fixture(root)
            pkg.write_json(evidence, {'sourceCommit':'different-commit', 'devices':{'fr265':review}})
            with self.assertRaisesRegex(ValueError, 'source commit differs'):
                pkg.approved_packages(root, evidence)
            pkg.write_json(evidence, {'sourceCommit':'test-commit', 'devices':{'epix2':review}})
            with self.assertRaisesRegex(ValueError, 'no successful compile'):
                pkg.approved_packages(root, evidence)

    def test_failed_release_upload_never_publishes_and_zip_is_allowlisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence, review, _ = self.evidence_fixture(root)
            folder = root / 'fr265'
            record = json.loads((folder / 'build-info.json').read_text())
            record['deviceName'] = 'Forerunner 265'
            pkg.write_json(folder / 'build-info.json', record)
            (folder / 'INSTALL.txt').write_text('test installation text')
            (folder / 'private-test-file.key').write_text('not a real key; must not be packaged')
            args = SimpleNamespace(output=str(root), evidence=str(evidence), tag='test-preview')
            with patch.object(pkg, 'git', return_value=b''), \
                 patch.object(pkg.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'gh')) as run:
                with self.assertRaises(subprocess.CalledProcessError):
                    pkg.publish(args)
                self.assertEqual(run.call_count, 1)
                self.assertIn('--draft', run.call_args.args[0])
            with pkg.zipfile.ZipFile(root / 'release/Prismelier-fr265-test-preview.zip') as archive:
                self.assertEqual(set(archive.namelist()),
                                 {'Prismelier-fr265.prg', 'build-info.json', 'INSTALL.txt', 'SHA256SUMS'})

    def test_all_matrix_models_match_existing_layout(self):
        matrix = json.loads((ROOT / 'packaging/devices.json').read_text())
        for device in matrix['devices']:
            self.assertEqual((device['width'], device['height'], device['shape'], device['display']),
                             (416, 416, 'round', 'AMOLED'))


if __name__ == '__main__':
    unittest.main()
