import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from backend import catalog, environment, loras, lora_validation as evidence, main, test_api

ENGINE = 'http://127.0.0.1:8188'


class LoraValidationTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def prepare(self):
        record = evidence.records()[0][0]
        catalog.merge(self.db, ENGINE, ['renamed-base.safetensors'])
        catalog.update_metadata(self.db, ENGINE, 'renamed-base.safetensors',
                                dict(architecture='sdxl', sha256=record['sha256']))
        loras.merge(self.db, ENGINE, ['renamed-lora.safetensors'])
        loras.update_metadata(self.db, ENGINE, 'renamed-lora.safetensors',
                              dict(architecture='sdxl', sha256=record['lora_sha256']))
        return dict(engine_url=ENGINE, checkpoint='renamed-base.safetensors',
                    lora=dict(name='renamed-lora.safetensors', enabled=True, strength_model=1.0, strength_clip=0.0),
                    settings=record['settings'])

    def test_readonly_hash_pair_and_exact_conditions_without_gpu_or_engine(self):
        payload = self.prepare()
        before = self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine contact')):
            response = self.client.post('/api/loras/validation', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        value = response.json()
        self.assertEqual(value['status'], 'recorded')
        self.assertEqual(len(value['matching_parameter_records']), 1)
        self.assertFalse(value['current_file_verified'])
        self.assertEqual(value['training_status'], 'unverified')
        self.assertIsNone(value['records'][0]['warm_engine_seconds'])
        self.assertEqual(self.db.read_bytes(), before)
        data = self.client.post('/api/loras/validation', json=payload | dict(engine_url=ENGINE+'/')).json()
        self.assertEqual(data['engine_url'], ENGINE)
        self.assertEqual(data['status'], 'recorded')

    def test_strength_resolution_sampler_changes_and_disabled_choice_never_match(self):
        payload = self.prepare()
        for change in [dict(settings=payload['settings'] | dict(width=1024)),
                       dict(settings=payload['settings'] | dict(sampler_name='euler')),
                       dict(lora=payload['lora'] | dict(strength_clip=1.0)),
                       dict(lora=payload['lora'] | dict(enabled=False))]:
            data = self.client.post('/api/loras/validation', json=payload | change).json()
            self.assertEqual(data['matching_parameter_records'], [])
        del payload['settings']
        data = self.client.post('/api/loras/validation', json=payload).json()
        self.assertEqual(data['status'], 'recorded')
        self.assertEqual(data['matching_parameter_records'], [])

    def test_animagine_evidence_is_separate_from_pony_and_exact_parameter_matches(self):
        payload = self.prepare()
        records, error = evidence.records()
        self.assertIsNone(error)
        record = next(v for v in records if v['model'] == 'Animagine XL 4.0 Opt')
        catalog.update_metadata(self.db, ENGINE, payload['checkpoint'], dict(sha256=record['sha256']))
        payload['settings'] = record['settings']
        before = self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('read-only evidence')):
            value = self.client.post('/api/loras/validation', json=payload).json()
            self.assertEqual(value['matching_parameter_records'], [record['id']])
            self.assertEqual([v['model'] for v in value['records']], ['Animagine XL 4.0 Opt'])
            changed = self.client.post('/api/loras/validation', json=payload | dict(
                settings=payload['settings'] | dict(width=768, height=768))).json()
            self.assertEqual(changed['matching_parameter_records'], [])
        self.assertEqual(self.db.read_bytes(), before)

    def test_missing_hash_changed_architecture_and_stale_catalog_do_not_verify(self):
        payload = self.prepare()
        for changes, status in [(dict(sha256=''), 'unverified'), (dict(sha256='f'*64), 'unverified'),
                                (dict(architecture='sd1'), 'incompatible')]:
            loras.update_metadata(self.db, ENGINE, payload['lora']['name'], changes)
            data = self.client.post('/api/loras/validation', json=payload).json()
            self.assertEqual(data['status'], status)
            self.assertEqual(data['records'], [])
        payload = self.prepare()
        loras.mutate(self.db, ENGINE, lambda value: value.update(sync_error='offline'))
        self.assertEqual(self.client.post('/api/loras/validation', json=payload).json()['status'], 'unverified')
        self.prepare()
        catalog.merge(self.db, ENGINE, [])
        self.assertEqual(self.client.post('/api/loras/validation', json=payload).json()['records'], [])

    def test_registry_errors_duplicate_oversize_and_unknown_fields_keep_state_unknown(self):
        payload = self.prepare()
        original = evidence.records()[0][0]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'records.json'
            for records in [[original, original], [original | dict(workflow='checkpoint-text2image-v1')],
                            [original | dict(strength_model=True)], [original | dict(extra='bad')],
                            [original | dict(lora_architecture='sd1')]]:
                path.write_text(json.dumps(dict(records=records)), encoding='utf-8')
                with patch.object(evidence, 'REGISTRY', path):
                    data = self.client.post('/api/loras/validation', json=payload).json()
                self.assertEqual(data['records'], [])
                self.assertIsNotNone(data['registry_error'])
            path.write_text(' ' * (256*1024+1))
            with patch.object(evidence, 'REGISTRY', path):
                self.assertEqual(evidence.records()[0], [])

    def test_scope_input_and_concurrent_registration_changes_are_rejected(self):
        payload = self.prepare()
        for change, code in [(dict(engine_url='http://127.0.0.1:9999'), 409),
                             (dict(checkpoint='absent'), 404), (dict(extra=True), 422),
                             (dict(lora=payload['lora'] | dict(strength_model=True)), 422),
                             (dict(settings=payload['settings'] | dict(width=True)), 422),
                             (dict(settings=payload['settings'] | dict(batch_size=True)), 422)]:
            self.assertEqual(self.client.post('/api/loras/validation', json=payload | change).status_code, code)
        original = evidence.evaluate
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            loras.update_metadata(self.db, ENGINE, payload['lora']['name'], dict(notes='concurrent edit'))
            return result
        with patch.object(evidence, 'evaluate', changed):
            self.assertEqual(self.client.post('/api/loras/validation', json=payload).status_code, 409)

    def test_advice_covers_only_specific_lora_conditions_and_rejects_racing_edits(self):
        payload = self.prepare()
        body = {k: v for k, v in payload['settings'].items() if k != 'batch_size'} | dict(
            engine_url=ENGINE, checkpoint=payload['checkpoint'], loras=[payload['lora']])
        report = dict(url=ENGINE, diagnostics=environment.engine_diagnostics(status='offline'))
        before = self.db.read_bytes()
        with patch.object(main, 'engine', AsyncMock(return_value=report)):
            data = self.client.post('/api/generation-advice', json=body).json()
            self.assertEqual(data['validation_status'], 'recorded')
            self.assertEqual(len(data['matching_parameter_records']), 1)
            data = self.client.post('/api/generation-advice', json=body | dict(steps=20)).json()
            self.assertEqual(data['matching_parameter_records'], [])
        self.assertEqual(before, self.db.read_bytes())
        async def changed():
            loras.update_metadata(self.db, ENGINE, payload['lora']['name'], dict(sha256='a'*64))
            return report
        with patch.object(main, 'engine', changed):
            self.assertEqual(self.client.post('/api/generation-advice', json=body).status_code, 409)


if __name__ == '__main__':
    unittest.main()
