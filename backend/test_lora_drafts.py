import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4

from backend import drafts, main, test_api, test_submissions, workflows


class LoraDraftTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def body(self, **changes):
        return dict(title='LoRA 草稿', engine_url='http://127.0.0.1:8188', checkpoint='test.safetensors',
                    prompt='a forest', seed='18446744073709551615',
                    loras=[dict(name='styles/ink.safetensors', enabled=True, strength_model=-0.75, strength_clip=0.125)]) | changes

    def test_save_reload_disable_and_remove_lora_without_loading_weights(self):
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('drafts must remain offline')):
            first = self.client.post('/api/drafts', json=self.body())
            self.assertEqual(first.status_code, 201, first.text)
            value = first.json()
            self.assertEqual(value['loras'], self.body()['loras'])
            self.assertEqual(self.client.get('/api/drafts').json()[0]['loras'], value['loras'])
            payload = self.body() | dict(revision=value['revision'])
            payload['loras'][0]['enabled'] = False
            updated = self.client.put('/api/drafts/' + value['id'], json=payload).json()
            self.assertEqual(updated['loras'][0], value['loras'][0] | dict(enabled=False))
            removed = self.client.put('/api/drafts/' + value['id'], json=self.body(loras=[], revision=updated['revision']))
            self.assertEqual(removed.status_code, 200, removed.text)
            self.assertEqual(removed.json()['loras'], [])

    def test_legacy_draft_defaults_are_read_only(self):
        value = self.body()
        value.pop('loras')
        old = drafts.save(self.db, value)
        with closing(sqlite3.connect(self.db)) as db:
            before = db.execute('SELECT value FROM settings').fetchone()[0]
        self.assertEqual(self.client.get('/api/drafts').json()[0]['loras'], [])
        self.assertNotIn('loras', drafts.list_all(self.db)[0])
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT value FROM settings').fetchone()[0], before)

    def test_invalid_single_lora_settings_do_not_create_drafts_or_jobs(self):
        choice = self.body()['loras'][0]
        bad = [[choice, choice], None, ['filename'], [choice | dict(name=' ')], [choice | dict(enabled=1)],
               [choice | dict(enabled='true')], [choice | dict(strength_model=True)], [choice | dict(strength_clip='1')],
               [choice | dict(strength_model=20.01)], [choice | dict(strength_clip=-20.01)],
               [choice | dict(strength_model=None)], [choice | dict(version='fake')]]
        with patch('backend.main.httpx.AsyncClient', side_effect=AssertionError('invalid input must not contact engine')):
            for values in bad:
                with self.subTest(values=values):
                    body = self.body(loras=values)
                    self.assertEqual(self.client.post('/api/drafts', json=body).status_code, 422)
                    self.assertEqual(self.client.post('/api/generate', json=body | dict(request_id=str(uuid4()))).status_code, 422)
        self.assertEqual(self.client.get('/api/drafts').json(), [])
        self.assertEqual(self.client.get('/api/jobs').json(), [])

    def test_enabled_lora_is_not_silently_dropped_if_loader_is_missing(self):
        remote = test_submissions.SubmissionTests.remote(self)
        with patch('backend.main.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/generate', json=self.body() | dict(request_id=str(uuid4())))
        self.assertEqual(result.status_code, 422)
        self.assertIn('LoraLoader', result.json()['detail']['message'])
        remote.post.assert_not_called()
        job = self.client.get('/api/jobs/' + result.json()['detail']['job_id']).json()
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['workflow']['8']['inputs']['lora_name'], self.body()['loras'][0]['name'])

    def test_disabled_lora_keeps_existing_workflow_and_seed(self):
        values = self.body()['loras']
        values[0]['enabled'] = False
        body = self.body(loras=values) | dict(request_id=str(uuid4()))
        remote = test_submissions.SubmissionTests.remote(self)
        with patch('backend.main.httpx.AsyncClient', return_value=remote):
            result = self.client.post('/api/generate', json=body)
        self.assertEqual(result.status_code, 200, result.text)
        expected = main.DraftInput.model_validate(body).model_dump()
        self.assertEqual(result.json()['workflow'], workflows.build(expected))
        self.assertEqual(len(result.json()['workflow']), 7)
        self.assertEqual(result.json()['workflow']['5']['inputs']['seed'], 2**64 - 1)
