import json
import unittest
from pathlib import Path
from unittest.mock import patch

from backend import catalog, main, test_api, validation_records as evidence


class ValidationRecordTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    sync = test_api.ApiTests.sync

    def model(self, **changes):
        self.sync(['renamed.safetensors'])
        return catalog.update_metadata(self.db, main.engine_url(), 'renamed.safetensors',
                                       dict(architecture='sdxl', sha256=evidence.records()[0][0]['sha256']) | changes)['models'][0]

    def test_exact_hash_and_architecture_match_only_recorded_conditions(self):
        result = evidence.evaluate(self.model())
        self.assertEqual(result['status'], 'verified')
        self.assertFalse(result['current_file_verified'])
        self.assertEqual(result['training_status'], 'unverified')
        record = result['records'][0]
        self.assertEqual(record['settings']['width'], 768)
        self.assertEqual(record['vram_bytes'], 12 * 1024 ** 3)
        self.assertEqual(record['sampled_device_peak_bytes'], 10451156992)
        self.assertEqual(record['sample_count'], 12)
        self.assertIn('不是最低', record['conditions'])
        for changes in ({'sha256': ''}, {'sha256': 'f' * 64}, {'architecture': 'unknown'}, {'architecture': 'sd1'}):
            self.assertEqual(evidence.evaluate(self.model(**changes))['status'], 'unverified')

    def test_names_and_versions_do_not_verify_and_unsupported_is_not_downgraded(self):
        for architecture in ('flux', 'sd3', 'other'):
            result = evidence.evaluate(self.model(architecture=architecture))
            self.assertEqual(result['status'], 'incompatible')
            self.assertEqual(result['records'], [])
        result = evidence.evaluate(dict(name='pony-v6-xl.safetensors', version='V6 XL', architecture='sdxl'))
        self.assertEqual(result['status'], 'unverified')

    def test_registry_errors_never_claim_verification(self):
        model = self.model()
        invalid = Path(self.temp.name) / 'bad.json'
        record = evidence.records()[0][0]
        for content in ('oops', json.dumps({'records': [record, record]}),
                        json.dumps({'records': [record | {'cold_wall_seconds': float('nan')}]}),
                        json.dumps({'records': [record | {'reference': 'https://untrusted.example'}]})):
            invalid.write_text(content, encoding='utf-8')
            with patch.object(evidence, 'REGISTRY', invalid):
                result = evidence.evaluate(model)
            self.assertEqual(result['status'], 'unverified')
            self.assertTrue(result['registry_error'])

    def test_readonly_route_scoped_without_engine_or_gpu_access(self):
        self.model()
        original = self.db.read_bytes()
        params = dict(engine_url=main.engine_url(), name='renamed.safetensors')
        with (patch.object(main.httpx, 'AsyncClient', side_effect=AssertionError('no network')),
              patch.object(main, 'gpu_info', side_effect=AssertionError('no GPU'))):
            response = self.client.get('/api/models/validation', params=params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'verified')
        self.assertEqual(self.db.read_bytes(), original)
        self.assertEqual(self.client.get('/api/models/validation', params=params | {'name': 'missing'}).status_code, 404)
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        self.assertEqual(self.client.get('/api/models/validation', params=params).status_code, 409)


if __name__ == '__main__':
    unittest.main()
