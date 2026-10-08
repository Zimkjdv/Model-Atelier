import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from backend.test_animagine_acceptance import AnimaginePlatform
from backend.test_generation_acceptance import Clock
from backend.workflows import build
from scripts import verify_multi_lora as acceptance, install_pony as downloader


class StylePlatform(AnimaginePlatform):
    def __init__(self, profile='multi', **options):
        super().__init__(**options)
        self.profile = profile
        self.settings = acceptance.settings(self.engine, self.checkpoint, profile)
        self.workflow = build(self.settings)
        by_name = {m['filename']: m for m in (acceptance.LCM, acceptance.STYLE)}
        self.loras = [choice | dict(version=by_name[choice['name']]['version'], architecture='sdxl',
                                   sha256=by_name[choice['name']]['sha256'], listed=True)
                      for choice in self.settings['loras']]

    def job(self):
        return super().job() | dict(lora_metadata=self.loras)

    def artwork(self):
        return super().artwork() | dict(lora_metadata=self.loras)

    def handle(self, request):
        if request.url.path == '/api/loras/sync':
            self.seen.append((request.method, request.url.path))
            return httpx.Response(200, json=dict(engine_url=self.engine, sync_error=None, loras=self.loras))
        response = super().handle(request)
        if request.url.path == '/api/engine/capabilities/sync':
            return httpx.Response(200, json=response.json() | dict(
                sampler_names=[self.settings['sampler_name']], schedulers=[self.settings['scheduler']]))
        return response


class MultiLoraAcceptanceTests(unittest.TestCase):
    def check(self, platform, previous=None):
        clock = Clock()
        cls = type('Fixed', (acceptance.StyleAcceptance,), dict(profile=platform.profile))
        with httpx.Client(base_url='http://127.0.0.1:8001', transport=httpx.MockTransport(platform.handle)) as client, \
             patch.object(Path, 'is_file', return_value=True), patch.object(downloader, '_verified', return_value=True):
            return cls(client, platform.engine, platform.checkpoint, clock=clock.now, sleep=clock.sleep).run(previous)

    def test_three_profiles_and_once_only_offline_ordered_snapshot_verification(self):
        for profile, count in [('baseline', 7), ('style', 8), ('multi', 9), ('multi-8', 9), ('style-lcm-8', 9)]:
            platform = StylePlatform(profile, lose_submission=True)
            original = self.check(platform)
            self.assertEqual(original['status'], 'passed', original)
            self.assertEqual(len(original['workflow']), count)
            self.assertEqual(platform.submissions, 1)
            platform.seen.clear()
            with patch.object(downloader, '_verified', side_effect=AssertionError('offline must not inspect weights')):
                result = self.check(platform, original)
            self.assertEqual(result['status'], 'passed', result)
            self.assertTrue(all(method == 'GET' for method, _ in platform.seen))

    def test_eight_step_profiles_change_only_steps_or_order_and_reject_other_report(self):
        old = acceptance.settings('http://127.0.0.1:8188', acceptance.MODEL['filename'], 'multi')
        eight = acceptance.settings('http://127.0.0.1:8188', acceptance.MODEL['filename'], 'multi-8')
        reverse = acceptance.settings('http://127.0.0.1:8188', acceptance.MODEL['filename'], 'style-lcm-8')
        self.assertEqual(eight['steps'], 8)
        self.assertEqual(reverse['loras'], list(reversed(eight['loras'])))
        for key in old:
            if key not in ('steps', 'title'): self.assertEqual(eight[key], old[key], key)
            if key not in ('loras', 'title'): self.assertEqual(reverse[key], eight[key], key)
        platform = StylePlatform('multi-8')
        previous = self.check(platform)
        other = StylePlatform('style-lcm-8')
        self.assertEqual(self.check(other, previous)['stage'], 'validate_report')
        self.assertEqual(other.seen, [])

    def test_order_strength_and_other_profile_cannot_be_reverified(self):
        platform = StylePlatform()
        original = self.check(platform)
        for change in ('order', 'strength', 'profile'):
            previous = copy.deepcopy(original)
            if change == 'order':
                previous['weight_snapshots']['lora_metadata'].reverse()
            elif change == 'strength':
                previous['weight_snapshots']['lora_metadata'][1]['strength_clip'] = True
            else:
                previous['settings']['loras'].pop()
            platform.seen.clear()
            result = self.check(platform, previous)
            self.assertEqual(result['stage'], 'validate_report', result)
            self.assertEqual(platform.seen, [])

    def test_style_install_uses_lora_path_and_unknown_license_provenance(self):
        content = b'fixed style fixture'
        manifest = acceptance.STYLE | dict(size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
        with tempfile.TemporaryDirectory() as temp, httpx.Client(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, stream=httpx.ByteStream(content)))) as client:
            result = downloader.install(workspace=Path(temp), manifest=manifest, client=client, output=lambda _: None)
            self.assertEqual((Path(temp) / 'runtime/ComfyUI/models/loras' / manifest['filename']).read_bytes(), content)
            self.assertFalse(result['license']['terms_verified'])
            self.assertFalse((Path(temp) / 'runtime/ComfyUI/models/checkpoints').exists())
