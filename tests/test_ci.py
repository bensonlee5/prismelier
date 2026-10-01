"""Offline checks for CI safety and diagnostics; never substitutes for a compile."""
import importlib.util
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ci_build', ROOT / 'tools' / 'ci_build.py')
ci = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ci)


class CiTests(unittest.TestCase):
    def test_missing_configuration_fails_closed(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(ci.platform, 'system', return_value='Linux'):
            with self.assertRaisesRegex(ValueError, 'CIQ_SDK is missing'):
                ci.preflight()

    def test_key_inside_repository_rejected_before_compiler(self):
        with patch.dict('os.environ', {'CIQ_SDK': '/no-sdk', 'CIQ_KEY': str(ROOT / 'bad.der')}, clear=True):
            with self.assertRaisesRegex(ValueError, 'outside the repository'):
                ci.preflight()

    def test_profile_fingerprint_is_content_sensitive_and_ordered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'b').write_text('test fixture, not a Garmin profile')
            (root / 'a').write_text('another fixture')
            first = ci.profile_digest(root)
            self.assertEqual(first, ci.profile_digest(root))
            (root / 'a').write_text('changed fixture')
            self.assertNotEqual(first, ci.profile_digest(root))

    def test_failed_compile_removes_old_outputs_and_cannot_stage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'build' / 'ci-artifact').mkdir(parents=True)
            (root / 'build' / 'Prismelier.prg').write_bytes(b'stale test fixture')
            (root / 'build' / 'ci-artifact' / 'Prismelier.prg').write_bytes(b'stale fixture')
            inputs = root / 'fixture-inputs'
            inputs.mkdir()
            (inputs / 'a').write_text('unit-test fingerprint fixture')
            with patch.object(ci, 'ROOT', root), patch.object(ci, 'preflight', return_value=(root, inputs)), \
                 patch.object(ci.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'fixture')):
                with self.assertRaises(subprocess.CalledProcessError):
                    ci.build()
            self.assertFalse((root / 'build' / 'Prismelier.prg').exists())
            self.assertFalse((root / 'build' / 'ci-artifact').exists())

    def test_manual_owner_main_only_and_pinned_actions(self):
        workflow = (ROOT / '.github' / 'workflows' / 'compile.yml').read_text()
        lines = [x for x in workflow.splitlines() if not x.lstrip().startswith('#')]
        body = '\n'.join(lines)
        self.assertIn('  workflow_dispatch:', body)
        for event in ('pull_request:', 'pull_request_target:', 'workflow_run:', 'push:'):
            self.assertNotIn(event, body)
        self.assertIn("github.ref == 'refs/heads/main'", body)
        self.assertIn('github.actor == github.repository_owner', body)
        self.assertIn('github.triggering_actor == github.repository_owner', body)
        self.assertIn('${{ github.run_attempt }}', body)
        self.assertIn('contents: read', body)
        self.assertNotIn(': write', body)
        self.assertIn('persist-credentials: false', body)
        self.assertIn('actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5', body)
        self.assertIn('actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02', body)
        self.assertIn('if-no-files-found: error', body)
        self.assertNotIn('secrets.', body)
        self.assertNotIn('continue-on-error', body)

    def test_artifact_upload_is_explicit_allowlist(self):
        workflow = (ROOT / '.github' / 'workflows' / 'compile.yml').read_text()
        paths = [line.strip() for line in workflow.splitlines() if 'build/ci-artifact/' in line]
        self.assertEqual(paths, ['build/ci-artifact/Prismelier.prg',
                                 'build/ci-artifact/SHA256SUMS',
                                 'build/ci-artifact/build-info.json'])


if __name__ == '__main__':
    unittest.main()
