"""More ordered stacks/strengths/seeds remain once-only and GET-only on recovery."""

import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import httpx
from backend import test_multi_lora_acceptance as old
from backend.test_generation_acceptance import Clock
from backend.workflows import build
from scripts import verify_style_matrix as study
from scripts import install_pony as downloader


class Platform(old.StylePlatform):
    def __init__(self, profile='pixel', seed=study.SEEDS[0], subject='anime-portrait', **options):
        super().__init__('baseline', **options)
        self.runner = type(
            'FixedStudy',
            (study.MatrixAcceptance,),
            dict(profile=profile, seed=seed, subject=subject),
        )
        instance = self.runner(None, self.engine, self.checkpoint)
        self.settings = instance.expected_settings()
        self.workflow = build(self.settings)
        manifests = {v['filename']: v for v in instance.manifests()[1:]}
        self.loras = [
            choice
            | dict(
                version=manifests[choice['name']]['version'],
                architecture='sdxl',
                sha256=manifests[choice['name']]['sha256'],
                listed=True,
            )
            for choice in self.settings['loras']
        ]

    def handle(self, request):
        response = super().handle(request)
        if request.url.path.endswith('/creation-settings'):
            return httpx.Response(200, json=response.json() | dict(lora_metadata=self.loras))
        return response


class StyleMatrixTests(unittest.TestCase):
    def check(self, platform, previous=None, verified=True):
        clock = Clock()
        with (
            httpx.Client(
                base_url='http://127.0.0.1:8001', transport=httpx.MockTransport(platform.handle)
            ) as client,
            patch.object(Path, 'is_file', return_value=True),
            patch.object(downloader, '_verified', return_value=verified),
        ):
            return platform.runner(
                client, platform.engine, platform.checkpoint, clock=clock.now, sleep=clock.sleep
            ).run(previous)

    def test_all_profiles_seeds_subjects_once_then_get_only(self):
        for profile in study.PROFILES:
            for seed in study.SEEDS:
                for subject in study.SUBJECTS:
                    platform = Platform(profile, seed, subject, lose_submission=True)
                    report = self.check(platform)
                    self.assertEqual(report['status'], 'passed', report)
                    self.assertEqual(platform.submissions, 1)
                    self.assertEqual(str(report['workflow']['5']['inputs']['seed']), seed)
                    self.assertEqual(len(report['workflow']), 7 + len(study.PROFILES[profile]))
                    platform.seen.clear()
                    with patch.object(
                        downloader, '_paths', side_effect=AssertionError('no offline weight reads')
                    ):
                        recovered = self.check(platform, report)
                    self.assertEqual(recovered['status'], 'passed', recovered)
                    self.assertTrue(all(method == 'GET' for method, _ in platform.seen))

    def test_order_strength_subject_seed_and_frozen_report_tampering_refuse_before_get(self):
        platform = Platform('lcm-ikea-pixel')
        original = self.check(platform)
        for field in ('order', 'strength', 'subject', 'seed', 'revision', 'restore'):
            report = copy.deepcopy(original)
            if field == 'order':
                report['weight_snapshots']['lora_metadata'].reverse()
            elif field == 'strength':
                report['weight_snapshots']['lora_metadata'][0]['strength_clip'] = True
            elif field == 'restore':
                report['verified_artworks'][0]['restore_settings']['lora_metadata'].reverse()
            else:
                key = 'source_revision' if field == 'revision' else field
                report['style_study'][key] = 'changed'
            platform.seen.clear()
            result = self.check(platform, report)
            self.assertEqual(result['status'], 'failed')
            self.assertEqual(platform.seen, [])

    def test_weight_failure_never_submits(self):
        platform = Platform('pixel')
        self.assertEqual(self.check(platform, verified=False)['status'], 'failed')
        self.assertEqual(platform.submissions, 0)

    def test_new_weight_installs_only_in_loras_and_fixed_source_cannot_be_changed(self):
        content = b'pixel lora installer fixture'
        manifest = study.convert_pixel_lora.SOURCE | dict(
            size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest()
        )
        with (
            tempfile.TemporaryDirectory() as temp,
            httpx.Client(
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, stream=httpx.ByteStream(content))
                )
            ) as client,
        ):
            result = downloader.install(
                workspace=Path(temp), manifest=manifest, client=client, output=lambda _: None
            )
            self.assertEqual(
                (Path(temp) / 'runtime/ComfyUI/models/loras' / manifest['filename']).read_bytes(),
                content,
            )
            self.assertFalse(result['license']['terms_verified'])
            self.assertFalse((Path(temp) / 'runtime/ComfyUI/models/checkpoints').exists())
        for changes in (
            dict(filename='../other'),
            dict(source=manifest['source'] | dict(revision='a' * 40)),
            dict(source=manifest['source'] | dict(download_url='https://example.org/weight')),
        ):
            with self.assertRaises(downloader.InstallationError):
                downloader.validate_manifest(manifest | changes)
