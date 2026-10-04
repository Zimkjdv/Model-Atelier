"""Fixed model acceptance must preserve bytes, identity and offline GET-only replay."""
import copy
import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from PIL import Image

from backend.test_generation_acceptance import Platform, Clock
from backend.workflows import build
from scripts import verify_animagine_generation as acceptance


class AnimaginePlatform(Platform):
    def __init__(self, **options):
        super().__init__(**options)
        self.checkpoint = acceptance.MODEL['filename']
        self.settings = acceptance.settings(self.engine, self.checkpoint)
        self.workflow = build(self.settings)
        self.job_version = self.artwork_version = acceptance.MODEL['version']
        self.metadata = dict(name=self.checkpoint, architecture='sdxl', version=self.job_version,
                             size_bytes=acceptance.MODEL['size_bytes'], sha256=acceptance.MODEL['sha256'])
        stream = io.BytesIO()
        Image.new('RGB', (1024, 1024), '#226699').save(stream, 'PNG')
        self.image = stream.getvalue()

    def job(self):
        return super().job() | dict(model_metadata=copy.deepcopy(self.metadata), lora_metadata=[])

    def artwork(self):
        return super().artwork() | dict(width=1024, height=1024, model_metadata=copy.deepcopy(self.metadata),
                                       lora_metadata=[])

    def handle(self, request):
        path = request.url.path
        if path in ('/api/models', '/api/models/sync', '/api/artworks/' + self.artwork_id + '/creation-settings'):
            self.seen.append((request.method, path))
            value = (dict(settings=self.settings | self.restore_override, model_version=self.job_version)
                     if path.endswith('/creation-settings') else dict(engine_url=self.engine, sync_error=None,
                               models=[self.metadata | dict(listed=True)]))
            return httpx.Response(200, json=value)
        response = super().handle(request)
        if path == '/api/engine/capabilities/sync':
            response = httpx.Response(200, json=response.json() | dict(
                sampler_names=['euler_ancestral'], schedulers=['normal']))
        return response


class AnimagineAcceptanceTests(unittest.TestCase):
    def run_check(self, platform, previous=None, *, local_valid=True, runner_type=acceptance.AnimagineAcceptance):
        clock, recorded = Clock(), []
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'model.safetensors'
            target.write_bytes(b'fixture')
            with httpx.Client(base_url='http://127.0.0.1:8001', transport=httpx.MockTransport(platform.handle)) as client, \
                    patch.object(acceptance.downloader, '_paths', return_value=(target, None, None, None)), \
                    patch.object(acceptance.downloader, '_verified', return_value=local_valid):
                runner = runner_type(client, platform.engine, platform.checkpoint,
                    clock=clock.now, sleep=clock.sleep, emit=lambda v: recorded.append(copy.deepcopy(v)))
                result = runner.run(previous)
        return result, recorded

    def test_complete_and_offline_get_only_verification_preserve_model_and_1024_image(self):
        platform = AnimaginePlatform(lose_submission=True)
        result, _ = self.run_check(platform)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(platform.submissions, 1)
        self.assertEqual(result['verified_artworks'][0]['width'], 1024)
        self.assertEqual(result['verified_artworks'][0]['sha256'], hashlib.sha256(platform.image).hexdigest())
        platform.seen.clear()
        with patch.object(acceptance.AnimagineAcceptance, 'preflight', side_effect=AssertionError('offline')):
            verified, _ = self.run_check(platform, result, local_valid=False)
        self.assertEqual(verified['status'], 'passed', verified)
        self.assertTrue(all(method == 'GET' for method, _ in platform.seen))
        self.assertEqual(platform.submissions, 1)

    def test_bad_local_hash_or_registered_identity_never_submits(self):
        for change in ('local', 'hash', 'architecture', 'version', 'size'):
            with self.subTest(change=change):
                platform = AnimaginePlatform()
                if change == 'hash':
                    platform.metadata['sha256'] = 'a'*64
                elif change == 'architecture':
                    platform.metadata['architecture'] = 'sd1'
                elif change == 'version':
                    platform.metadata['version'] = 'unknown'
                elif change == 'size':
                    platform.metadata['size_bytes'] += 1
                result, _ = self.run_check(platform, local_valid=change != 'local')
                self.assertEqual(result['status'], 'failed')
                self.assertEqual(platform.submissions, 0)

    def test_invalid_report_is_not_emitted_or_queried(self):
        platform = AnimaginePlatform()
        original, _ = self.run_check(platform)
        for field in ('dimensions', 'snapshot', 'settings'):
            value = copy.deepcopy(original)
            if field == 'dimensions':
                value['verified_artworks'][0]['width'] = 768
            elif field == 'snapshot':
                value['model_snapshot']['sha256'] = 'b'*64
            else:
                value['settings']['steps'] = 20
            platform.seen.clear()
            result, recorded = self.run_check(platform, value)
            self.assertEqual(result['stage'], 'validate_report')
            self.assertEqual(recorded, [])
            self.assertEqual(platform.seen, [])

    def test_unsupported_checkpoint_is_rejected_before_generation(self):
        with self.assertRaises(ValueError):
            acceptance.settings('http://127.0.0.1:8188', 'pony-v6-xl.safetensors')

    def test_repeat_seed_is_exact_and_reports_cannot_cross_profiles(self):
        platform = AnimaginePlatform()
        platform.settings['seed'] = str(int(acceptance.base.SEED) + 1)
        platform.workflow = build(platform.settings)
        value, _ = self.run_check(platform, runner_type=acceptance.RepeatAcceptance)
        self.assertEqual(value['status'], 'passed', value)
        self.assertEqual(value['workflow']['5']['inputs']['seed'], 9007199254740994)
        platform.seen.clear()
        failed, emitted = self.run_check(platform, value)
        self.assertEqual(failed['stage'], 'validate_report')
        self.assertEqual(emitted, [])
        self.assertEqual(platform.seen, [])
