import unittest
from unittest.mock import AsyncMock, patch
from backend import catalog, environment, generation_advice as advice, main, test_api, validation_records


class AdviceTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    sync = test_api.ApiTests.sync

    def setup_model(self):
        self.sync(['model.safetensors'])
        record = validation_records.records()[0][0]
        catalog.update_metadata(self.db, main.engine_url(), 'model.safetensors',
                                dict(architecture='sdxl', sha256=record['sha256']))
        return dict(engine_url=main.engine_url(), checkpoint='model.safetensors',
                    **{k: v for k, v in record['settings'].items() if k != 'batch_size'})

    def report(self, offline=False):
        stats = dict(system={}, devices=[dict(name='Small GPU', type='cuda', vram_total=1024, vram_free=0)])
        return dict(url=main.engine_url(), diagnostics=environment.scoped_engine_diagnostics(
            stats, main.engine_url(), main.engine_url(), 'offline' if offline else 'available'))

    def test_zero_free_memory_does_not_gate_or_mutate(self):
        payload = self.setup_model()
        original = self.db.read_bytes()
        with patch.object(main, 'engine', AsyncMock(return_value=self.report())):
            response = self.client.post('/api/generation-advice', json=payload)
        self.assertEqual(response.status_code, 200)
        value = response.json()
        self.assertTrue(value['advisory_only'])
        self.assertNotIn('allows_submission', value)
        self.assertIsNone(value['estimated_vram_bytes'])
        self.assertEqual(len(value['matching_parameter_records']), 1)
        self.assertEqual(value['diagnostics']['devices'][0]['vram']['free'], 0)
        self.assertEqual(self.db.read_bytes(), original)

    def test_changed_parameters_and_offline_still_return_advice(self):
        payload = self.setup_model() | {'width': 1024}
        with patch.object(main, 'engine', AsyncMock(return_value=self.report(True))):
            value = self.client.post('/api/generation-advice', json=payload).json()
        self.assertEqual(value['matching_parameter_records'], [])
        self.assertTrue(any('離線' in warning for warning in value['warnings']))
        self.assertTrue(any('不在' in warning for warning in value['warnings']))

    def test_unknown_identity_never_claims_parameter_verification(self):
        payload = self.setup_model()
        catalog.update_metadata(self.db, main.engine_url(), 'model.safetensors', dict(sha256=''))
        with patch.object(main, 'engine', AsyncMock(return_value=self.report())):
            value = self.client.post('/api/generation-advice', json=payload).json()
        self.assertEqual(value['validation_status'], 'unverified')
        self.assertEqual(value['matching_parameter_records'], [])

    def test_engine_switch_or_metadata_change_rejects_stale_advice(self):
        payload = self.setup_model()
        async def changed():
            report = self.report()
            catalog.update_metadata(self.db, main.engine_url(), 'model.safetensors', dict(sha256='f' * 64))
            return report
        with patch.object(main, 'engine', changed):
            self.assertEqual(self.client.post('/api/generation-advice', json=payload).status_code, 409)
        with patch.object(main, 'engine', AsyncMock(return_value=self.report() | {'url': 'http://127.0.0.1:9000'})):
            self.assertEqual(self.client.post('/api/generation-advice', json=payload).status_code, 409)

    def test_invalid_parameters_and_missing_model_do_not_query_engine(self):
        payload = self.setup_model()
        with patch.object(main, 'engine', AsyncMock(side_effect=AssertionError('must not query'))):
            for change in ({'width': 0}, {'steps': True}, {'cfg': 'nan'}, {'prompt': 'unexpected'}):
                self.assertEqual(self.client.post('/api/generation-advice', json=payload | change).status_code, 422)
            self.assertEqual(self.client.post('/api/generation-advice', json=payload | {'checkpoint': 'missing'}).status_code, 404)


if __name__ == '__main__':
    unittest.main()
