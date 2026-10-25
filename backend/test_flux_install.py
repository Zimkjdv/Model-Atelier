import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from contextlib import redirect_stdout, redirect_stderr
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx

from backend import flux_plan
from scripts import install_flux as flux, install_model, install_pony as downloader


class FluxInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = copy.deepcopy(flux_plan.manifest())
        pinned = copy.deepcopy(flux_plan.PINNED)
        self.payloads = {}
        for row in self.plan['components']:
            payload = ('synthetic FLUX fixture: ' + row['role']).encode()
            self.payloads[row['filename']] = payload
            row.update(size_bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            pinned[row['role']] = pinned[row['role']][:4] + (row['size_bytes'], row['sha256'])
        self.patches = [
            patch.object(flux_plan, 'manifest', return_value=self.plan),
            patch.object(flux_plan, 'PINNED', pinned),
            patch.object(flux.storage, 'volume_identity', return_value=('volume1', 'C:\\')),
            patch.object(
                downloader.shutil, 'disk_usage', return_value=SimpleNamespace(free=100 * 1024**3)
            ),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.seen = []

    def remote(self, request):
        self.seen.append(request)
        filename = request.url.path.rsplit('/', 1)[-1]
        payload = self.payloads[filename]
        headers = {'Content-Length': str(len(payload))}
        if request.method == 'HEAD':
            return httpx.Response(200, headers=headers)
        if 'range' in request.headers:
            offset = int(request.headers['range'].split('=')[1].split('-')[0])
            headers.update(
                {
                    'Content-Range': f'bytes {offset}-{len(payload) - 1}/{len(payload)}',
                    'Content-Length': str(len(payload) - offset),
                }
            )
            return httpx.Response(206, headers=headers, stream=httpx.ByteStream(payload[offset:]))
        return httpx.Response(200, headers=headers, stream=httpx.ByteStream(payload))

    def install(self, handler=None, **kwargs):
        with flux.source_client(
            'hf_fixture_secret', transport=httpx.MockTransport(handler or self.remote)
        ) as client:
            return flux.install(workspace=self.root, client=client, output=lambda _: None, **kwargs)

    def paths(self, role):
        value = next(
            row for row in flux.component_manifests() if downloader.FLUX_IDS[row['id']] == role
        )
        return downloader._paths(self.root, value['filename'])

    def test_four_pinned_components_download_to_their_categories_and_verify_offline(self):
        result = self.install()
        self.assertTrue(result['current_files_verified'])
        self.assertFalse(result['generation_verified'])
        self.assertIsNone(result['minimum_vram_bytes'])
        self.assertEqual([r.method for r in self.seen], ['HEAD'] * 4 + ['GET'] * 4)
        for row in self.plan['components']:
            target = self.root / 'runtime/ComfyUI/models' / row['category'] / row['filename']
            self.assertEqual(target.read_bytes(), self.payloads[row['filename']])
            receipt = json.loads(
                target.with_name(target.name + '.provenance.json').read_text('utf-8')
            )
            self.assertEqual(receipt['source']['revision'], row['revision'])
            self.assertEqual(receipt['sha256'], row['sha256'])
            self.assertEqual(
                receipt['license']['terms_verified'], row['role'] in ('diffusion_model', 'vae')
            )
            self.assertNotIn('hf_fixture_secret', json.dumps(receipt))
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        report = flux.local_report(self.root, verify=True)
        self.assertTrue(report['current_files_verified'])
        self.assertEqual(
            before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        )
        self.seen.clear()
        self.assertTrue(self.install()['current_files_verified'])
        self.assertEqual(self.seen, [])

    def test_gate_denial_checks_every_source_before_any_payload_or_directory_write(self):
        def gated(request):
            self.seen.append(request)
            return httpx.Response(401 if 'black-forest-labs' in request.url.path else 200)

        with self.assertRaisesRegex(downloader.InstallationError, '未開始下載'):
            self.install(gated)
        self.assertEqual([r.method for r in self.seen], ['HEAD'] * 4)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_auth_only_goes_to_fixed_bfl_paths_and_never_to_redirect_cdn_or_public_encoder(self):
        requests = []

        def redirect(request):
            requests.append(request)
            if 'black-forest-labs' in request.url.path:
                self.assertEqual(request.headers.get('authorization'), 'Bearer hf_fixture_secret')
                return httpx.Response(
                    302, headers={'Location': 'https://cdn.example/weight?signature=private'}
                )
            self.assertNotIn('authorization', request.headers)
            return httpx.Response(200)

        with flux.source_client(
            'hf_fixture_secret', transport=httpx.MockTransport(redirect)
        ) as client:
            self.assertTrue(all(r['state'] == 'accessible' for r in flux.check_access(client)))
            client.get('https://huggingface.co/unrelated', headers={'Authorization': 'stale'})
            with self.assertRaisesRegex(downloader.InstallationError, 'HTTPS'):
                client.get('http://huggingface.co/unrelated')
        self.assertEqual(sum(r.url.host == 'cdn.example' for r in requests), 2)
        self.assertFalse(any(r.url.scheme != 'https' for r in requests))

    def test_redirect_downgrade_never_sent(self):
        def redirect(request):
            self.seen.append(request)
            return httpx.Response(302, headers={'Location': 'http://cdn.example/weight'})

        with self.assertRaisesRegex(downloader.InstallationError, 'HTTPS'):
            self.install(redirect)
        self.assertEqual(len(self.seen), 1)
        self.assertFalse((self.root / 'runtime').exists())

    def test_partial_resumes_exact_range_and_still_requires_full_sha256(self):
        target, partial, _, _ = self.paths('diffusion_model')
        partial.write_bytes(self.payloads[target.name][:9])
        result = self.install()
        self.assertTrue(result['current_files_verified'])
        request = next(r for r in self.seen if r.method == 'GET')
        self.assertEqual(request.headers.get('range'), 'bytes=9-')
        self.assertFalse(partial.exists())

    def test_hash_mismatch_never_publishes_and_restart_is_per_role(self):
        target, partial, _, _ = self.paths('diffusion_model')
        partial.write_bytes(b'x' * len(self.payloads[target.name]))
        _, other_partial, _, _ = self.paths('vae')
        other_partial.write_bytes(self.payloads['ae.safetensors'][:4])
        with self.assertRaisesRegex(downloader.InstallationError, 'SHA-256'):
            self.install()
        self.assertFalse(target.exists())
        self.assertEqual(other_partial.stat().st_size, 4)
        self.seen.clear()
        self.install(restart_roles=('diffusion_model',))
        gets = [r for r in self.seen if r.method == 'GET']
        self.assertNotIn('range', gets[0].headers)
        self.assertEqual(gets[1].headers.get('range'), 'bytes=4-')

    def test_existing_wrong_hash_is_not_overwritten(self):
        target, _, _, _ = self.paths('vae')
        target.write_bytes(b'x' * len(self.payloads[target.name]))
        self.assertFalse(flux.local_report(self.root)['current_files_verified'])
        self.assertEqual(
            next(
                r
                for r in flux.local_report(self.root, verify=True)['components']
                if r['role'] == 'vae'
            )['state'],
            'hash_mismatch',
        )
        with self.assertRaises(downloader.InstallationError):
            self.install(restart_roles=('vae',))
        self.assertEqual(target.read_bytes(), b'x' * len(self.payloads[target.name]))
        self.assertFalse(any(r.method == 'GET' for r in self.seen))

    def test_check_does_not_hash_or_write_and_all_components_share_one_reserve(self):
        with patch.object(downloader, '_hash', side_effect=AssertionError('unexpected hash')):
            report = flux.local_report(self.root)
        self.assertFalse(report['current_files_verified'])
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(len(report['volumes']), 1)
        self.assertEqual(
            report['volumes'][0]['required_bytes'],
            report['total_size_bytes'] + downloader.RESERVE_BYTES,
        )

    def test_combined_budget_blocks_when_each_individual_file_would_fit(self):
        largest = max(r['size_bytes'] for r in self.plan['components'])
        with patch.object(
            downloader.shutil,
            'disk_usage',
            return_value=SimpleNamespace(free=largest + downloader.RESERVE_BYTES),
        ):
            with self.assertRaises(downloader.InstallationError):
                self.install()
        self.assertFalse(any(r.method == 'GET' for r in self.seen))
        self.assertFalse((self.root / 'runtime').exists())

    def test_disk_budget_accounts_for_partial_without_claiming_verified(self):
        target, partial, _, lock = self.paths('t5xxl')
        partial.write_bytes(self.payloads[target.name][:7])
        report = flux.local_report(self.root)
        self.assertEqual(
            report['volumes'][0]['download_remaining_bytes'], report['total_size_bytes'] - 7
        )
        self.assertFalse(report['current_files_verified'])
        lock.write_text('another installer')
        with self.assertRaises(downloader.InstallationError):
            self.install()
        self.assertEqual(lock.read_text(), 'another installer')
        self.assertFalse(target.exists())

    def test_oversized_partial_needs_explicit_restart_and_never_overwrites_final(self):
        target, partial, _, _ = self.paths('clip_l')
        partial.write_bytes(b'x' * 100)
        self.assertFalse(flux.ready(flux.local_report(self.root)))
        self.install(restart_roles=('clip_l',))
        self.assertEqual(target.read_bytes(), self.payloads[target.name])

    def test_source_size_mismatch_and_private_network_errors_are_sanitized(self):
        def remote(request):
            if 'black-forest-labs' in request.url.path:
                raise httpx.ReadError(
                    'hf_private_secret signed_url?secret=private', request=request
                )
            return httpx.Response(200, headers={'Content-Length': '999999'})

        with flux.source_client(
            'hf_fixture_secret', transport=httpx.MockTransport(remote)
        ) as client:
            report = flux.check_access(client)
        self.assertEqual(
            [r['state'] for r in report], ['unknown', 'unknown', 'size_mismatch', 'size_mismatch']
        )
        self.assertNotIn('secret', json.dumps(report))
        self.assertNotIn('signed_url', json.dumps(report))

    def test_manifest_cannot_change_hash_source_or_size_and_generic_cli_directs_to_flux_tool(self):
        value = flux.component_manifests()[0]
        for key, bad in [('sha256', '0' * 64), ('size_bytes', 1)]:
            with self.assertRaises(downloader.InstallationError):
                downloader.validate_manifest(value | {key: bad})
        with self.assertRaises(downloader.InstallationError):
            downloader.validate_manifest(
                value | {'source': value['source'] | {'revision': '0' * 40}}
            )
        with self.assertRaisesRegex(downloader.InstallationError, 'install_flux'):
            install_model.manifest(value['id'])

    def test_terms_review_distinguishes_author_weights_from_untraced_packaging(self):
        rows = flux.component_manifests()
        self.assertEqual(
            [row['license']['terms_verified'] for row in rows], [True, True, False, False]
        )
        self.plan['components'][0]['license_review'] = None
        with self.assertRaises(downloader.InstallationError):
            flux.component_manifests()
        self.assertEqual(list(self.root.iterdir()), [])

    def test_verify_cli_never_reads_credentials_or_connects(self):
        output = io.StringIO()
        with (
            patch.object(downloader, 'WORKSPACE', self.root),
            patch.object(flux, 'read_token', side_effect=AssertionError('credentials')),
            patch.object(flux, 'source_client', side_effect=AssertionError('network')),
            redirect_stdout(output),
        ):
            code = flux.main(['verify'])
        self.assertEqual(code, 2)
        self.assertFalse(json.loads(output.getvalue())['current_files_verified'])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_cli_network_exception_never_prints_signed_url_or_token(self):
        error = io.StringIO()
        with (
            patch.object(flux, 'read_token', return_value='hf_fixture_secret'),
            patch.object(
                flux,
                'source_client',
                side_effect=httpx.InvalidURL('private?token=hf_fixture_secret'),
            ),
            redirect_stderr(error),
        ):
            self.assertEqual(flux.main(['install']), 1)
        self.assertNotIn('hf_fixture_secret', error.getvalue())
        self.assertNotIn('private?', error.getvalue())

    def test_token_precedence_standard_cache_and_malformed_token_never_printed(self):
        hf_dir = self.root / 'hf-cache'
        hf_dir.mkdir()
        (hf_dir / 'token').write_text('hf_cached_fixture\n')
        with patch.dict(os.environ, {'HF_HOME': str(hf_dir)}, clear=True):
            self.assertEqual(flux.read_token(), 'hf_cached_fixture')
            with patch.dict(os.environ, {'HF_TOKEN': 'hf_env_fixture'}):
                self.assertEqual(flux.read_token(), 'hf_env_fixture')
            token_path = hf_dir / 'separate-token'
            token_path.write_text('hf_other_fixture')
            with patch.dict(os.environ, {'HF_TOKEN_PATH': str(token_path)}):
                self.assertEqual(flux.read_token(), 'hf_other_fixture')
            with patch.dict(os.environ, {'HF_TOKEN': 'hf_invalid\nsecret'}):
                error = io.StringIO()
                with redirect_stderr(error):
                    self.assertEqual(flux.main(['check']), 1)
                self.assertNotIn('secret', error.getvalue())
            (hf_dir / 'token').write_bytes(b'x' * 4097)
            with self.assertRaises(downloader.InstallationError):
                flux.read_token()


if __name__ == '__main__':
    unittest.main()
