import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from backend import catalog, environment, loras, main, stack_validation as evidence, test_api

ENGINE = 'http://127.0.0.1:8188'


class StackEvidenceTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def prepare(self):
        record = evidence.records()[0][0]
        catalog.merge(self.db, ENGINE, ['base'])
        catalog.update_metadata(self.db, ENGINE, 'base', dict(architecture='sdxl', sha256=record['sha256']))
        names = ['first', 'second']
        loras.merge(self.db, ENGINE, names)
        for name, entry in zip(names, record['loras']):
            loras.update_metadata(self.db, ENGINE, name, dict(architecture='sdxl', sha256=entry['sha256']))
        return dict(engine_url=ENGINE, checkpoint='base', settings=record['settings'], loras=[
            dict(name=name, enabled=True, strength_model=v['strength_model'], strength_clip=v['strength_clip'])
            for name,v in zip(names,record['loras'])])

    def test_only_ordered_hashes_and_exact_strengths_match_readonly(self):
        body = self.prepare(); before = self.db.read_bytes()
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('no engine')):
            value = self.client.post('/api/loras/stack-validation', json=body).json()
            self.assertEqual(value['status'], 'recorded')
            self.assertEqual(len(value['matching_parameter_records']), 1)
            self.assertFalse(value['current_file_verified'])
            self.assertIn('對比不足',value['records'][0]['quality_observation'])
            for change in [dict(loras=list(reversed(body['loras']))), dict(loras=body['loras'][:1]+[body['loras'][1]|dict(enabled=False)])]:
                changed = self.client.post('/api/loras/stack-validation',json=body|change).json()
                self.assertEqual(changed['records'],[])
            for change in [dict(settings=body['settings']|dict(steps=8)),
                           dict(loras=[body['loras'][0]|dict(strength_model=.5),body['loras'][1]])]:
                value = self.client.post('/api/loras/stack-validation',json=body|change).json()
                self.assertEqual(value['status'],'recorded')
                self.assertEqual(value['matching_parameter_records'],[])
        self.assertEqual(before,self.db.read_bytes())

    def test_missing_stale_wrong_architecture_and_race_never_borrow_evidence(self):
        body = self.prepare()
        for change,status in [(dict(sha256='f'*64),'unverified'),(dict(architecture='sd1'),'incompatible')]:
            loras.update_metadata(self.db,ENGINE,'second',change)
            value=self.client.post('/api/loras/stack-validation',json=body).json()
            self.assertEqual(value['status'],status); self.assertEqual(value['records'],[])
        self.prepare(); loras.mutate(self.db,ENGINE,lambda v:v.update(sync_error='offline'))
        self.assertEqual(self.client.post('/api/loras/stack-validation',json=body).json()['records'],[])
        self.prepare(); original=evidence.evaluate
        def race(*args,**kwargs):
            result=original(*args,**kwargs)
            loras.update_metadata(self.db,ENGINE,'second',dict(notes='changed'))
            return result
        with patch.object(evidence,'evaluate',race):
            self.assertEqual(self.client.post('/api/loras/stack-validation',json=body).status_code,409)
        for change,code in [(dict(engine_url=ENGINE+'/wrong'),409),(dict(checkpoint='absent'),404),
                            (dict(loras=[body['loras'][0]]*2),422),(dict(settings=body['settings']|dict(batch_size=True)),422)]:
            self.assertEqual(self.client.post('/api/loras/stack-validation',json=body|change).status_code,code)

    def test_invalid_registry_is_unknown_not_partial(self):
        original=evidence.records()[0][0]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'registry.json'
            duplicate=copy.deepcopy(original); duplicate['loras'][1]=duplicate['loras'][0]
            for records in [[original,original],[duplicate],[original|dict(wall_seconds=True)],
                            [original|dict(extra=True)]]:
                path.write_text(json.dumps(dict(records=records)),encoding='utf-8')
                with patch.object(evidence,'REGISTRY',path):
                    values,error=evidence.records()
                self.assertEqual(values,[]); self.assertIsNotNone(error)

    def test_advice_uses_stack_scope_and_rejects_concurrent_registration(self):
        body=self.prepare(); report=dict(url=ENGINE,diagnostics=environment.engine_diagnostics(status='offline'))
        body={k:v for k,v in body.items() if k!='settings'}|{k:v for k,v in body['settings'].items() if k!='batch_size'}
        with patch.object(main,'engine',AsyncMock(return_value=report)):
            data=self.client.post('/api/generation-advice',json=body).json()
            self.assertEqual(data['validation_status'],'recorded')
            self.assertEqual(len(data['matching_parameter_records']),1)
            self.assertIsNone(data['estimated_vram_bytes'])
            self.assertTrue(any('對比不足' in v for v in data['warnings']))
            self.assertEqual(self.client.post('/api/generation-advice',json=body|dict(loras=list(reversed(body['loras'])))).json()['matching_parameter_records'],[])
        async def race():
            loras.update_metadata(self.db,ENGINE,'second',dict(sha256='f'*64)); return report
        with patch.object(main,'engine',race):
            self.assertEqual(self.client.post('/api/generation-advice',json=body).status_code,409)
