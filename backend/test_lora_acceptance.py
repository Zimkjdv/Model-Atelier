"""Single-LoRA acceptance integrity and safe offline verification contracts."""
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from backend.test_generation_acceptance import Platform, Clock
from backend.workflows import build
from scripts import verify_lora_generation as lcm, install_model, install_pony as downloader


def registered(manifest):
    return dict(name=manifest['filename'], version=manifest['version'], architecture='sdxl',
                sha256=manifest['sha256'], listed=True)


class LoraPlatform(Platform):
    def __init__(self, **options):
        super().__init__(**options)
        self.settings = lcm.settings(self.engine, self.checkpoint)
        self.workflow = build(self.settings)
        self.lora = registered(lcm.LORA) | dict(enabled=True, strength_model=1.0, strength_clip=0.0)
        self.model = registered(lcm.CHECKPOINT)

    def job(self):
        return super().job() | dict(model_metadata=self.model, lora_metadata=[self.lora])

    def artwork(self):
        return super().artwork() | dict(model_metadata=self.model, lora_metadata=[self.lora])

    def handle(self, request):
        path = request.url.path
        if path in ('/api/models', '/api/loras/sync'):
            self.seen.append((request.method, path))
            value = dict(engine_url=self.engine, sync_error=None,
                         **({'models': [self.model]} if path == '/api/models' else {'loras': [self.lora]}))
            return httpx.Response(200, json=value)
        response = super().handle(request)
        if path == '/api/engine/capabilities/sync':
            return httpx.Response(200, json=response.json() | dict(sampler_names=['lcm'], schedulers=['sgm_uniform']))
        return response


class LoraAcceptanceTests(unittest.TestCase):
    def run_check(self, platform, previous=None, files_ok=True):
        clock = Clock()
        with httpx.Client(base_url='http://127.0.0.1:8000', transport=httpx.MockTransport(platform.handle)) as client, \
             patch.object(Path, 'is_file', return_value=True), patch.object(downloader, '_verified', return_value=files_ok):
            runner = lcm.LoraAcceptance(client, platform.engine, platform.checkpoint, clock=clock.now, sleep=clock.sleep)
            return runner.run(previous)

    def test_lost_response_once_and_offline_full_snapshot_restore(self):
        platform = LoraPlatform(lose_submission=True)
        original = self.run_check(platform)
        self.assertEqual(original['status'], 'passed', original)
        self.assertEqual(len(original['workflow']), 8)
        self.assertEqual(original['workflow']['5']['inputs']['model'], ['8', 0])
        self.assertEqual(platform.submissions, 1)
        platform.seen.clear()
        with patch.object(downloader, '_verified', side_effect=AssertionError('offline must not inspect weights')):
            verified = self.run_check(platform, previous=original)
        self.assertEqual(verified['status'], 'passed', verified)
        self.assertTrue(all(method == 'GET' for method, _ in platform.seen))
        self.assertEqual(verified['weight_snapshots'], original['weight_snapshots'])

    def test_invalid_local_weights_and_registered_identity_stop_before_submit(self):
        platform = LoraPlatform()
        value = self.run_check(platform, files_ok=False)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(platform.submissions, 0)
        platform.lora['sha256'] = 'a'*64
        value = self.run_check(platform)
        self.assertEqual(value['status'], 'failed')
        self.assertEqual(platform.submissions, 0)

    def test_original_snapshot_tampering_is_not_accepted_offline(self):
        platform = LoraPlatform()
        original = self.run_check(platform)
        self.assertEqual(original['status'], 'passed')
        for field, change in [('sha256', 'a'*64), ('strength_model', 0.5), ('version', 'different')]:
            value = copy.deepcopy(original)
            value['weight_snapshots']['lora_metadata'][0][field] = change
            platform.seen.clear()
            result = self.run_check(platform, previous=value)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(platform.seen, [])

    def test_changed_saved_snapshot_and_restored_strength_fail(self):
        platform = LoraPlatform()
        original = self.run_check(platform)
        platform.lora['captured_at'] = 'changed'
        self.assertEqual(self.run_check(platform, previous=original)['status'], 'failed')
        platform.lora.pop('captured_at')
        platform.restore_override = dict(loras=[dict(name=lcm.LORA['filename'], enabled=True, strength_model=0.3, strength_clip=0.0)])
        self.assertEqual(self.run_check(platform, previous=original)['status'], 'failed')

    def test_installer_targets_lora_directory_and_records_fixed_source(self):
        content = b'public LoRA fixture'
        manifest = install_model.manifest('lcm-lora-sdxl') | dict(size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
        with tempfile.TemporaryDirectory() as directory, httpx.Client(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, stream=httpx.ByteStream(content)))) as client:
            result = downloader.install(workspace=Path(directory), manifest=manifest, client=client, output=lambda _: None)
            target = Path(directory) / 'runtime/ComfyUI/models/loras' / manifest['filename']
            self.assertEqual(target.read_bytes(), content)
            self.assertTrue(result['verified'])
            self.assertFalse((Path(directory) / 'runtime/ComfyUI/models/checkpoints').exists())


if __name__ == '__main__':
    unittest.main()
