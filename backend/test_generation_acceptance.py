"""Acceptance CLI contracts; no GPU, local service or real generation required."""
import copy
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import httpx
from PIL import Image

from backend.workflows import build
from scripts import verify_local_generation as acceptance


class Clock:
    def __init__(self):
        self.value = 0.0
        self.sleeps = []

    def now(self):
        return self.value

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.value += seconds


class Platform:
    def __init__(self, *, lose_submission=False, import_error=False, never_finish=False):
        self.engine = 'http://127.0.0.1:8188'
        self.checkpoint = 'pony-v6-xl.safetensors'
        self.seen = []
        self.submissions = 0
        self.refreshes = 0
        self.lose_submission = lose_submission
        self.import_error = import_error
        self.never_finish = never_finish
        self.artwork_id = str(uuid4())
        self.settings = acceptance.settings(self.engine, self.checkpoint)
        self.workflow = build(self.settings)
        self.job_id = None
        self.restore_override = {}
        self.bad_seed = False
        self.device_type = 'cuda'
        self.job_version = self.artwork_version = '未知'
        self.history_success = True
        stream = io.BytesIO()
        Image.new('RGB', (768, 768), '#567852').save(stream, 'PNG')
        self.image = stream.getvalue()

    def job(self):
        workflow = copy.deepcopy(self.workflow)
        if self.bad_seed:
            workflow['5']['inputs']['seed'] = int(float(acceptance.SEED))
        completed = self.refreshes >= 2 and not self.never_finish
        return dict(id=self.job_id, prompt_id=self.job_id, engine_url=self.engine,
                    checkpoint=self.checkpoint, status='completed' if completed else 'running',
                    model_version=self.job_version, workflow=workflow, history={
                        'status': {'completed': completed, 'status_str': 'success' if self.history_success else 'error'},
                        'outputs': {'7': {'images': [{'filename': 'result.png', 'subfolder': '', 'type': 'output'}]}}})

    def artwork(self):
        return dict(id=self.artwork_id, job_id=self.job_id, engine_url=self.engine,
                    checkpoint=self.checkpoint, model_version=self.artwork_version, width=768, height=768,
                    image_available=True, sha256=hashlib.sha256(self.image).hexdigest())

    def handle(self, request):
        path = request.url.path
        self.seen.append((request.method, path))
        if path == '/api/health':
            value = {'status': 'ok'}
        elif path == '/api/settings':
            value = {'comfy_url': self.engine}
        elif path == '/api/engine':
            value = {'url': self.engine, 'connected': True,
                     'stats': {'system': {'comfyui_version': '0.34.0'}, 'devices': [{'type': self.device_type, 'name': 'Mock NVIDIA'}]}}
        elif path == '/api/system':
            value = {'gpus': [{'index': '0', 'name': 'Mock NVIDIA', 'used': 123 + self.refreshes}], 'gpu_error': None}
        elif path == '/api/models/sync':
            value = {'engine_url': self.engine, 'sync_error': None,
                     'models': [{'name': self.checkpoint, 'listed': True, 'version': ''}]}
        elif path == '/api/engine/capabilities/sync':
            value = {'engine_url': self.engine, 'available': True, 'stale': False, 'engine_matches': True,
                     'sampler_names': ['dpmpp_2m'], 'schedulers': ['karras'],
                     'bounds': {'steps': {'min': 1, 'max': 150}, 'cfg': {'min': 0, 'max': 30}, 'denoise': {'min': 0, 'max': 1}}}
        elif path == '/api/generate':
            self.submissions += 1
            submitted = json.loads(request.content)
            self.job_id = submitted['request_id']
            if {key: value for key, value in submitted.items() if key != 'request_id'} != self.settings:
                raise AssertionError('Acceptance parameters changed')
            if self.lose_submission:
                raise httpx.ReadTimeout('response lost after acceptance', request=request)
            value = self.job()
        elif path == '/api/jobs/' + str(self.job_id) + '/refresh':
            self.refreshes += 1
            value = self.job()
        elif path == '/api/jobs/' + str(self.job_id) + '/artworks':
            value = {'imported': [self.artwork()], 'existing': [],
                     'errors': [{'message': 'save failed'}] if self.import_error else []}
        elif path == '/api/jobs/' + str(self.job_id):
            value = self.job()
        elif path == '/api/jobs/' + str(self.job_id) + '/workflow':
            value = self.workflow
        elif path == '/api/artworks/' + self.artwork_id:
            value = self.artwork()
        elif path == '/api/artworks/' + self.artwork_id + '/workflow':
            value = self.workflow
        elif path == '/api/artworks/' + self.artwork_id + '/image':
            return httpx.Response(200, content=self.image, headers={'content-type': 'image/png'})
        elif path == '/api/artworks/' + self.artwork_id + '/creation-settings':
            value = {'settings': self.settings | self.restore_override, 'model_version': '未知'}
        else:
            raise AssertionError('Unexpected acceptance request: ' + request.method + ' ' + path)
        return httpx.Response(200, json=value)


class GenerationAcceptanceTests(unittest.TestCase):
    def run_check(self, platform, previous=None, **options):
        clock = Clock()
        recorded = []
        with httpx.Client(base_url='http://127.0.0.1:8000', transport=httpx.MockTransport(platform.handle)) as client:
            runner = acceptance.Acceptance(client, platform.engine, platform.checkpoint,
                                           emit=lambda value: recorded.append(copy.deepcopy(value)),
                                           clock=clock.now, sleep=clock.sleep, **options)
            value = runner.run(previous)
        return value, clock, recorded

    def test_complete_acceptance_preserves_precision_restore_and_unknown_version(self):
        platform = Platform()
        value, clock, recorded = self.run_check(platform)
        self.assertEqual(value['status'], 'passed', value)
        self.assertEqual(platform.submissions, 1)
        self.assertEqual(value['settings']['seed'], '9007199254740993')
        self.assertIs(type(value['workflow']['5']['inputs']['seed']), int)
        self.assertEqual(value['workflow']['5']['inputs']['seed'], 9007199254740993)
        self.assertEqual(value['model_version'], '未知')
        self.assertEqual(value['verified_artworks'][0]['width'], 768)
        self.assertEqual(clock.sleeps, [2.0])
        self.assertEqual(value['submission_to_history_wall_seconds'], 2.0)
        self.assertIn('not pure GPU', value['timing_scope'])
        self.assertEqual(value['vram_sampling']['requested_interval_seconds'], 2.0)
        self.assertEqual(value['vram_sampling']['sampled_max_used_bytes_by_gpu'], {'0': 124})
        before_submit = next(item for item in recorded if item['stage'] == 'submit_once')
        self.assertEqual(before_submit['job_id'], value['job_id'])
        self.assertEqual(before_submit['request_id'], value['job_id'])

    def test_submission_timeout_never_reposts_even_when_original_job_succeeds(self):
        platform = Platform(lose_submission=True)
        value, _, _ = self.run_check(platform)
        self.assertEqual(value['status'], 'passed', value)
        self.assertEqual(platform.submissions, 1)
        self.assertIn('submission_transport_error', value)
        self.assertEqual(sum(path == '/api/generate' for _, path in platform.seen), 1)

    def test_poll_deadline_keeps_uuid_and_never_replays(self):
        platform = Platform(lose_submission=True, never_finish=True)
        value, clock, _ = self.run_check(platform, max_wait=4)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['stage'], 'poll_history')
        self.assertEqual(value['job_id'], platform.job_id)
        self.assertEqual(platform.submissions, 1)
        self.assertEqual(clock.value, 4.0)
        self.assertIn('deadline', value['error'])

    def test_partial_import_errors_fail_even_with_http200_and_one_saved_image(self):
        platform = Platform(import_error=True)
        value, _, _ = self.run_check(platform)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['stage'], 'import_artworks')
        self.assertEqual(value['import_response']['errors'], [{'message': 'save failed'}])
        self.assertEqual(value['job_id'], platform.job_id)
        self.assertEqual(platform.submissions, 1)
        self.assertNotIn(('GET', '/api/artworks/' + platform.artwork_id + '/image'), platform.seen)

    def test_report_verification_only_gets_saved_outputs_without_engine_or_sync(self):
        platform = Platform()
        original, _, _ = self.run_check(platform)
        self.assertEqual(original['status'], 'passed')
        platform.seen.clear()
        value, _, _ = self.run_check(platform, previous=original)
        self.assertEqual(value['status'], 'passed', value)
        self.assertEqual(value['mode'], 'verify_report')
        self.assertTrue(platform.seen)
        self.assertTrue(all(method == 'GET' for method, _ in platform.seen))
        self.assertFalse(any(path in ('/api/engine', '/api/system', '/api/settings', '/api/health') for _, path in platform.seen))
        self.assertEqual(platform.submissions, 1)
        self.assertEqual(value['verified_artworks'][0]['sha256'], original['verified_artworks'][0]['sha256'])

    def test_workflow_precision_or_restore_changes_fail_without_another_generation(self):
        for change in ('workflow', 'restore'):
            with self.subTest(change=change):
                platform = Platform()
                if change == 'workflow':
                    platform.bad_seed = True
                else:
                    platform.restore_override['seed'] = int(acceptance.SEED)
                value, _, _ = self.run_check(platform)
                self.assertEqual(value['status'], 'failed')
                self.assertIn('seed', value['error'])
                self.assertEqual(platform.submissions, 1)

    def test_report_path_is_confined_to_runtime_and_urls_are_loopback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(acceptance, 'ROOT', Path(directory)):
            self.assertEqual(acceptance.report_path('runtime/check.json'), Path(directory) / 'runtime' / 'check.json')
            for path in ('README.json', '../outside.json', 'runtime/check.txt'):
                with self.assertRaises(ValueError):
                    acceptance.report_path(path)
        for url in ('http://example.com:8000', 'http://127.0.0.1:8000/path', 'http://user@localhost:8000', 'http://localhost'):
            with self.assertRaises(ValueError):
                acceptance.local_url(url)

    def test_cpu_fallback_is_not_recorded_as_successful_nvidia_generation(self):
        platform = Platform()
        platform.device_type = 'cpu'
        value, _, _ = self.run_check(platform)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(value['stage'], 'preflight')
        self.assertIsNone(value['job_id'])
        self.assertIn('CUDA', value['error'])
        self.assertEqual(platform.submissions, 0)

    def test_invalid_verify_report_is_not_emitted_or_read_from_platform(self):
        platform = Platform()
        original, _, _ = self.run_check(platform)
        for change in ('schema', 'settings', 'job_id', 'artwork_id', 'checksum', 'bytes', 'version', 'workflow', 'type'):
            with self.subTest(change=change):
                value = copy.deepcopy(original)
                if change == 'schema':
                    value['schema_version'] = 2
                elif change == 'settings':
                    value['settings']['prompt'] = 'different'
                elif change == 'job_id':
                    value['job_id'] = 'invalid'
                elif change == 'artwork_id':
                    value['artwork_ids'] = ['invalid']
                elif change == 'checksum':
                    value['verified_artworks'][0]['sha256'] = 'invalid'
                elif change == 'bytes':
                    value['verified_artworks'][0]['bytes'] = 0
                elif change == 'version':
                    value['model_version'] = 'unrelated-version'
                elif change == 'workflow':
                    value['workflow']['5']['inputs']['seed'] = int(float(acceptance.SEED))
                elif change == 'type':
                    value['settings']['width'] = 768.0
                platform.seen.clear()
                result, _, emitted = self.run_check(platform, previous=value)
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(result['stage'], 'validate_report')
                self.assertEqual(emitted, [])
                self.assertEqual(platform.seen, [])

    def test_original_checksum_detects_changed_image_even_when_database_hash_also_changes(self):
        platform = Platform()
        original, _, _ = self.run_check(platform)
        stream = io.BytesIO()
        Image.new('RGB', (768, 768), '#223399').save(stream, 'PNG')
        platform.image = stream.getvalue()
        value, _, _ = self.run_check(platform, previous=original)
        self.assertEqual(value['status'], 'failed')
        self.assertIn('original verified report', value['error'])
        self.assertEqual(value['verified_artworks'], original['verified_artworks'])
        self.assertEqual(platform.submissions, 1)

    def test_verification_requires_original_job_artwork_version_and_success_history(self):
        for change in ('job_version', 'artwork_version', 'history', 'bytes'):
            with self.subTest(change=change):
                platform = Platform()
                original, _, _ = self.run_check(platform)
                if change == 'job_version':
                    platform.job_version = 'changed'
                elif change == 'artwork_version':
                    platform.artwork_version = 'changed'
                elif change == 'history':
                    platform.history_success = False
                else:
                    original['verified_artworks'][0]['bytes'] += 1
                value, _, _ = self.run_check(platform, previous=original)
                self.assertEqual(value['status'], 'failed')
                self.assertEqual(platform.submissions, 1)

    def test_legacy_schema1_report_without_artwork_version_remains_compatible(self):
        platform = Platform()
        original, _, _ = self.run_check(platform)
        original['verified_artworks'][0].pop('model_version')
        value, _, _ = self.run_check(platform, previous=original)
        self.assertEqual(value['status'], 'passed', value)
        self.assertEqual(value['verified_artworks'][0]['model_version'], '未知')

    def test_atomic_writer_ignores_predictable_tmp_and_rejects_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(acceptance, 'ROOT', Path(directory)):
            path = acceptance.report_path('runtime/check.json')
            path.parent.mkdir()
            legacy_tmp = path.with_name(path.name + '.tmp')
            legacy_tmp.write_text('do not modify', encoding='utf-8')
            acceptance.write_report(path, {'valid': True})
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), {'valid': True})
            self.assertEqual(legacy_tmp.read_text(encoding='utf-8'), 'do not modify')
            original = path.read_bytes()
            # Portable simulated lstat result: Windows may not grant symlink
            # creation privileges, but the guard must reject the same result.
            with patch.object(Path, 'is_symlink', lambda candidate: candidate == path):
                with self.assertRaises(ValueError):
                    acceptance.write_report(path, {'valid': False})
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError):
                acceptance.write_report(Path(directory) / 'outside.json', {'bad': True})

    def test_cli_invalid_input_json_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(acceptance, 'ROOT', Path(directory)):
            path = acceptance.report_path('runtime/check.json')
            path.parent.mkdir()
            raw = '{"schema_version":2,"job_id":"do-not-overwrite"}'
            path.write_text(raw, encoding='utf-8')
            with httpx.Client(base_url='http://127.0.0.1:8000', transport=httpx.MockTransport(
                    lambda request: (_ for _ in ()).throw(AssertionError('invalid report must not contact API')))) as client:
                with patch('scripts.verify_local_generation.httpx.Client', return_value=client), patch('builtins.print'):
                    result = acceptance.main(['--report', str(path), '--verify-report'])
            self.assertEqual(result, 1)
            self.assertEqual(path.read_text(encoding='utf-8'), raw)

    def test_two_processes_cannot_reserve_same_report_before_generation(self):
        code = (
            'import sys\nfrom pathlib import Path\nfrom scripts import verify_local_generation as a\n'
            'a.ROOT=Path(sys.argv[1])\n'
            'try:\n a.reserve_report(Path(sys.argv[2]))\n'
            'except FileExistsError:\n raise SystemExit(2)\n'
            'with (a.ROOT / "runtime" / "submit-markers.txt").open("a") as f: f.write("once\\n")\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'runtime' / 'check.json'
            processes = [subprocess.Popen([sys.executable, '-c', code, str(root), str(path)],
                         cwd=acceptance.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0) for _ in range(2)]
            for process in processes:
                _, stderr = process.communicate(timeout=30)
                self.assertIn(process.returncode, (0, 2), stderr.decode(errors='replace'))
            self.assertEqual(sorted(process.returncode for process in processes), [0, 2])
            self.assertEqual((root / 'runtime' / 'submit-markers.txt').read_text().splitlines(), ['once'])


if __name__ == '__main__':
    unittest.main()
