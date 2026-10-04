import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend import flux_plan, main, test_api
from scripts import flux_preflight


class FluxPlanTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def root(self):
        return Path(self.temp.name)

    def read(self, free=100_000_000_000):
        with patch('backend.flux_plan.storage.volume_identity', return_value=('volume1', 'C:\\')):
            with patch('backend.flux_plan.shutil.disk_usage', return_value=SimpleNamespace(free=free)):
                return flux_plan.report(self.root())

    def test_pinned_source_and_all_dependencies_are_explicit_and_unsupported(self):
        report = self.read()
        self.assertEqual(len(report['components']), 4)
        self.assertEqual(report['total_size_bytes'], 29521303916)
        self.assertEqual(report['space_status'], 'sufficient')
        self.assertFalse(report['current_files_verified'])
        self.assertFalse(report['generation_supported'])
        self.assertFalse(report['download_supported'])
        self.assertIsNone(report['minimum_vram_bytes'])
        self.assertIsNone(report['minimum_ram_bytes'])
        for row in report['components']:
            self.assertIn(row['revision'], row['source_url'])
            self.assertTrue(row['version'].startswith('revision '))
            self.assertEqual(len(row['sha256']), 64)
            self.assertEqual(row['state'], 'missing')
            self.assertFalse(row['sha256_verified'])
        self.assertEqual(report['components'][0]['access'], 'hf_gated_user_review')

    def test_no_network_no_database_changes_and_no_directory_creation(self):
        before = sorted(str(p.relative_to(self.root())) for p in self.root().rglob('*'))
        database = self.db.read_bytes()
        with patch.object(main, 'ROOT', self.root()), patch('httpx.AsyncClient', side_effect=AssertionError('no network')):
            response = self.client.get('/api/model-plans/flux1-schnell')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.read_bytes(), database)
        self.assertEqual(before, sorted(str(p.relative_to(self.root())) for p in self.root().rglob('*')))
        self.assertFalse((self.root() / 'runtime').exists())

    def test_volume_reserve_once_and_zero_free_is_not_unknown(self):
        value = self.read(0)
        self.assertEqual(value['space_status'], 'insufficient')
        self.assertEqual(len(value['volumes']), 1)
        self.assertEqual(value['volumes'][0]['free_bytes'], 0)
        self.assertEqual(value['volumes'][0]['required_bytes'], value['total_size_bytes'] + flux_plan.RESERVE_BYTES)

    def test_distinct_volumes_are_not_summed_as_one_install_budget(self):
        for category in ('diffusion_models', 'vae', 'text_encoders'):
            (self.root() / 'runtime' / 'ComfyUI' / 'models' / category).mkdir(parents=True)
        def identity(path):
            return ('encoders', 'D:\\') if path.name == 'text_encoders' else ('main', 'C:\\')
        with patch('backend.flux_plan.storage.volume_identity', side_effect=identity), patch('backend.flux_plan.shutil.disk_usage', return_value=SimpleNamespace(free=30_000_000_000)):
            value = flux_plan.report(self.root())
        self.assertEqual(len(value['volumes']), 2)
        self.assertEqual(sum(v['required_bytes'] for v in value['volumes']), value['total_size_bytes'] + 2 * flux_plan.RESERVE_BYTES)

    def test_same_size_file_is_still_unverified_and_budget_is_conservative(self):
        value = flux_plan.manifest()
        value['components'][0]['size_bytes'] = 3
        pinned = copy.deepcopy(flux_plan.PINNED)
        previous = pinned['diffusion_model']
        pinned['diffusion_model'] = previous[:4] + (3, previous[5])
        target = self.root() / 'runtime' / 'ComfyUI' / 'models' / 'diffusion_models' / previous[1]
        target.parent.mkdir(parents=True)
        target.write_bytes(b'bad')
        with patch('backend.flux_plan.manifest', return_value=value):
            report = self.read()
        row = report['components'][0]
        self.assertEqual(row['state'], 'present_unverified')
        self.assertFalse(row['sha256_verified'])
        self.assertEqual(row['actual_size_bytes'], 3)
        self.assertEqual(report['volumes'][0]['required_bytes'], report['total_size_bytes'] + flux_plan.RESERVE_BYTES)
        self.assertEqual(target.read_bytes(), b'bad')

    def test_size_mismatch_is_reported_without_replacement(self):
        name = flux_plan.PINNED['diffusion_model'][1]
        target = self.root() / 'runtime' / 'ComfyUI' / 'models' / 'diffusion_models' / name
        target.parent.mkdir(parents=True)
        target.write_bytes(b'invalid')
        report = self.read()
        self.assertEqual(report['components'][0]['state'], 'size_mismatch')
        self.assertEqual(target.read_bytes(), b'invalid')

    def test_unreadable_volume_remains_unknown_instead_of_zero(self):
        with patch('backend.flux_plan.storage.volume_identity', side_effect=OSError('private error')):
            report = flux_plan.report(self.root())
        self.assertEqual(report['space_status'], 'unknown')
        self.assertEqual(report['volumes'], [])
        self.assertTrue(all(row['state'] == 'unknown' for row in report['components']))
        self.assertNotIn('private error', json.dumps(report))

    def test_directory_in_place_of_file_is_unknown_and_not_removed(self):
        target = self.root() / 'runtime' / 'ComfyUI' / 'models' / 'vae' / 'ae.safetensors'
        target.mkdir(parents=True)
        value = self.read()
        self.assertEqual(value['components'][1]['state'], 'unknown')
        self.assertEqual(value['space_status'], 'unknown')
        self.assertTrue(target.is_dir())

    def test_corrupted_manifest_or_identity_is_rejected(self):
        source = flux_plan.manifest()
        candidates = []
        for field, replacement in (('filename', '../../outside'), ('revision', 'main'), ('repository', 'other/repo'), ('size_bytes', True), ('sha256', 'a'*64)):
            value = copy.deepcopy(source)
            value['components'][0][field] = replacement
            candidates.append(value)
        value = copy.deepcopy(source)
        value['components'][3] = copy.deepcopy(value['components'][0])
        candidates.extend([value, {}, []])
        path = self.root() / 'plan.json'
        for value in candidates:
            path.write_text(json.dumps(value), encoding='utf-8')
            with patch.object(flux_plan, 'MANIFEST', path):
                with self.assertRaises((ValueError, TypeError)):
                    flux_plan.manifest()
        path.write_text('{broken', encoding='utf-8')
        with patch.object(flux_plan, 'MANIFEST', path):
            self.assertEqual(self.client.get('/api/model-plans/flux1-schnell').status_code, 503)

    def test_cli_reports_readonly_status_with_meaningful_exit_codes(self):
        for state, expected in [('sufficient', 0), ('insufficient', 2), ('unknown', 2)]:
            output = io.StringIO()
            with patch.object(flux_plan, 'report', return_value=dict(space_status=state)), redirect_stdout(output):
                self.assertEqual(flux_preflight.main(), expected)
            self.assertEqual(json.loads(output.getvalue())['space_status'], state)
