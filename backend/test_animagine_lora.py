import copy
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.test_animagine_acceptance import AnimaginePlatform
from backend.test_generation_acceptance import Clock
from backend.workflows import build
from scripts import verify_animagine_lora as acceptance, verify_lora_generation as pony


class LoraPlatform(AnimaginePlatform):
    def __init__(self, **options):
        super().__init__(**options)
        self.settings = acceptance.settings(self.engine, self.checkpoint)
        self.workflow = build(self.settings)
        self.lora = dict(name=pony.LORA['filename'], version=pony.LORA['version'], architecture='sdxl',
                         sha256=pony.LORA['sha256'], enabled=True, strength_model=1.0, strength_clip=0.0)

    def job(self):
        return super().job() | dict(lora_metadata=[self.lora])

    def artwork(self):
        return super().artwork() | dict(lora_metadata=[self.lora])

    def handle(self, request):
        if request.url.path == '/api/loras/sync':
            self.seen.append((request.method, request.url.path))
            return httpx.Response(200, json=dict(engine_url=self.engine, sync_error=None,
                                                loras=[self.lora | dict(listed=True)]))
        response = super().handle(request)
        if request.url.path == '/api/engine/capabilities/sync':
            return httpx.Response(200, json=response.json() | dict(sampler_names=['lcm'], schedulers=['sgm_uniform']))
        return response


class AnimagineLoraTests(unittest.TestCase):
    def run_check(self, platform, previous=None):
        clock = Clock()
        with httpx.Client(base_url='http://127.0.0.1:8001', transport=httpx.MockTransport(platform.handle)) as client, \
                patch.object(Path, 'is_file', return_value=True), \
                patch.object(pony.downloader, '_verified', return_value=True):
            runner = acceptance.AnimagineLoraAcceptance(client, platform.engine, platform.checkpoint,
                                                        clock=clock.now, sleep=clock.sleep)
            return runner.run(previous)

    def test_real_contract_lost_response_and_get_only_reverification(self):
        platform = LoraPlatform(lose_submission=True)
        result = self.run_check(platform)
        self.assertEqual(result['status'], 'passed', result)
        self.assertEqual(len(result['workflow']), 8)
        self.assertEqual(result['workflow']['1']['inputs']['ckpt_name'], acceptance.animagine.MODEL['filename'])
        self.assertEqual(result['verified_artworks'][0]['width'], 1024)
        platform.seen.clear()
        with patch.object(acceptance.AnimagineLoraAcceptance, 'preflight', side_effect=AssertionError('offline')):
            verified = self.run_check(platform, result)
        self.assertEqual(verified['status'], 'passed', verified)
        self.assertEqual(platform.submissions, 1)
        self.assertTrue(all(method == 'GET' for method, _ in platform.seen))

    def test_pony_snapshot_and_changed_lora_strength_cannot_verify_animagine(self):
        platform = LoraPlatform()
        result = self.run_check(platform)
        for field in ('checkpoint', 'strength'):
            previous = copy.deepcopy(result)
            if field == 'checkpoint':
                previous['weight_snapshots']['model_metadata'].update(
                    name=pony.CHECKPOINT['filename'], version=pony.CHECKPOINT['version'], sha256=pony.CHECKPOINT['sha256'])
            else:
                previous['weight_snapshots']['lora_metadata'][0]['strength_clip'] = 1.0
            platform.seen.clear()
            failed = self.run_check(platform, previous)
            self.assertEqual(failed['stage'], 'validate_report')
            self.assertEqual(platform.seen, [])
