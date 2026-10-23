import copy
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
import httpx
from backend import assets
from backend import test_control_edge_acceptance as old
from scripts import verify_pony_canny_loras as check


class PonyPlatform(old.EdgePlatform):
    def __init__(self, profile='baseline', **kwargs):
        super().__init__(**kwargs)
        self.runner = type(
            'FixedPony',
            (check.PonyCannyAcceptance,),
            dict(profile=profile, source_id=self.source_id, source_sha256=self.refs[0]['sha256']),
        )
        self.settings = self.runner(None, self.engine, self.checkpoint).expected_settings()
        self.lora_entries = [
            dict(
                name=m['filename'],
                version=m['version'],
                architecture='sdxl',
                sha256=m['sha256'],
                size_bytes=m['size_bytes'],
                listed=True,
            )
            for m in check.PROFILES[profile]
        ]

    def snapshots(self):
        return super().snapshots() | dict(
            lora_metadata=[
                metadata | choice
                for metadata, choice in zip(self.lora_entries, self.settings['loras'])
            ]
        )

    def handle(self, request):
        path = request.url.path
        if path == '/api/loras/sync':
            self.seen.append((request.method, path))
            return httpx.Response(
                200,
                json=dict(
                    engine_url=self.engine,
                    synced_at='time',
                    sync_error=None,
                    loras=self.lora_entries,
                ),
            )
        response = super().handle(request)
        if path == '/api/engine/capabilities/sync':
            return httpx.Response(
                200,
                json=response.json()
                | dict(sampler_names=['dpmpp_2m', 'lcm'], schedulers=['karras', 'sgm_uniform']),
            )
        if path.endswith('/creation-settings'):
            return httpx.Response(
                200, json=response.json() | dict(lora_metadata=self.snapshots()['lora_metadata'])
            )
        return response


class PonyCannyTests(unittest.TestCase):
    run_check = old.EdgeAcceptanceTests.run_check

    def test_fixed_source_fixture_normalizes_to_anchor_and_mismatch_never_submits(self):
        raw = (
            Path(__file__).resolve().parents[1] / 'experiments/fixtures/canny-chair-v1.png'
        ).read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            database = folder / 'test.sqlite3'
            with closing(sqlite3.connect(database)) as db, db:
                db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            item = assets.create(database, folder / 'assets', raw, 'chair.png')
            self.assertEqual(item['sha256'], check.PonyCannyAcceptance.source_sha256)
            self.assertEqual((item['width'], item['height']), (768, 768))
        platform = PonyPlatform()
        platform.runner.source_sha256 = check.PonyCannyAcceptance.source_sha256
        result, _ = self.run_check(platform)
        self.assertEqual(result['status'], 'failed')
        self.assertIsNone(result['job_id'])
        self.assertEqual(platform.submissions, 0)

    def test_five_profiles_submit_once_and_verify_original_edge_and_loras_with_gets(self):
        for profile in check.PROFILES:
            platform = PonyPlatform(profile, lose_submission=True)
            report, _ = self.run_check(platform)
            self.assertEqual(report['status'], 'passed', report)
            self.assertEqual(platform.submissions, 1)
            self.assertEqual(platform.edge_imports, 1)
            self.assertEqual(len(report['workflow']), 12 + len(check.PROFILES[profile]))
            self.assertEqual(report['settings']['seed'], '9007199254740993')
            self.assertEqual(report['lora_metadata'], platform.snapshots()['lora_metadata'])
            platform.seen.clear()
            verified, _ = self.run_check(platform, report, verified=False)
            self.assertEqual(verified['status'], 'passed', verified)
            self.assertTrue(all(method == 'GET' for method, _ in platform.seen))
            self.assertEqual(platform.submissions, 1)

    def test_tampered_order_hash_strength_or_restoration_rejects_before_any_request(self):
        platform = PonyPlatform('lcm-style')
        original, _ = self.run_check(platform)
        self.assertEqual(original['status'], 'passed', original)
        for kind in ('order', 'hash', 'strength', 'restore'):
            value = copy.deepcopy(original)
            if kind == 'order':
                value['lora_metadata'].reverse()
            elif kind == 'hash':
                value['lora_metadata'][0]['sha256'] = 'f' * 64
            elif kind == 'strength':
                value['lora_metadata'][0]['strength_clip'] = True
            else:
                value['verified_artworks'][0]['restore_settings']['lora_metadata'] = []
            platform.seen.clear()
            result, emitted = self.run_check(platform, value)
            self.assertEqual(result['stage'], 'validate_report', result)
            self.assertEqual(platform.seen, [])
            self.assertEqual(emitted, [])

    def test_missing_weight_or_wrong_lora_registration_never_admits_job(self):
        platform = PonyPlatform('style')
        result, _ = self.run_check(platform, verified=False)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(platform.submissions, 0)
        platform.lora_entries[0]['sha256'] = 'f' * 64
        result, _ = self.run_check(platform)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(platform.submissions, 0)

    def test_profiles_keep_same_source_prompt_control_and_exact_seed(self):
        platform = PonyPlatform()
        baseline = platform.settings
        for profile in check.PROFILES:
            runner = type(
                'Profile',
                (check.PonyCannyAcceptance,),
                dict(profile=profile, source_id=platform.source_id),
            )
            value = runner(None, platform.engine, platform.checkpoint).expected_settings()
            for key in (
                'prompt',
                'negative_prompt',
                'image_asset_id',
                'reference_ids',
                'reference_resize',
                'seed',
                'width',
                'height',
                'control_net_name',
                'control_strength',
                'control_start',
                'control_end',
                'canny_low',
                'canny_high',
                'denoise',
            ):
                self.assertEqual(value[key], baseline[key])
