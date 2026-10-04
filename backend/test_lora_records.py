import copy
import io
import json
import sqlite3
import unittest
from contextlib import closing
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4
from PIL import Image

from backend import catalog, gallery, jobs, lora_records, loras, main, progress, test_api, workflows
from backend import test_lora_submissions as submissions_tests

ENGINE, NAME = submissions_tests.ENGINE, submissions_tests.NAME


class LoraRecordTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    body = submissions_tests.LoraSubmissionTests.body
    prepare = submissions_tests.LoraSubmissionTests.prepare
    remote = submissions_tests.LoraSubmissionTests.remote
    submit = submissions_tests.LoraSubmissionTests.submit

    def job(self, **changes):
        self.prepare()
        loras.update_metadata(self.db, ENGINE, NAME, dict(version='LoRA v1', sha256='a'*64,
            source_url='https://example.org/lora-v1', license_name='custom', license_url='https://example.org/terms'))
        result = self.submit(self.body() | changes, self.remote())
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def artwork(self, job):
        raw = io.BytesIO()
        Image.new('RGB', (400, 300), '#718d76').save(raw, 'PNG')
        source = dict(node_id='7', filename='lora-result.png', subfolder='', type='output')
        return gallery.save(self.db, main.DATA / 'artworks', job, source, raw.getvalue())[0]

    def rows(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT key,value FROM settings ORDER BY key').fetchall()

    def test_submit_import_and_replay_preserve_original_version_and_settings(self):
        body = self.body()
        job = self.job(**body)
        snapshot = copy.deepcopy(job['lora_metadata'])
        self.assertEqual(snapshot[0]['name'], NAME)
        self.assertEqual(snapshot[0]['version'], 'LoRA v1')
        self.assertEqual(snapshot[0]['strength_model'], -.75)
        self.assertEqual(snapshot[0]['strength_clip'], .125)
        self.assertEqual(snapshot[0]['origin'], 'user_registered')
        self.assertTrue(snapshot[0]['enabled'])
        self.assertIsNotNone(datetime.fromisoformat(snapshot[0]['captured_at']).tzinfo)
        loras.update_metadata(self.db, ENGINE, NAME, dict(version='LoRA v2', sha256='b'*64, architecture='sd1'))
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no replay')):
            repeated = self.client.post('/api/generate', json=body).json()
        self.assertEqual(repeated['lora_metadata'], snapshot)
        self.assertEqual(self.client.get('/api/jobs').json()[0]['lora_metadata'], snapshot)
        self.assertEqual(progress.summary(repeated)['lora_metadata'], snapshot)
        item = self.artwork(job)
        self.assertEqual(item['lora_metadata'], snapshot)
        for path in ('/api/artworks', '/api/artworks/' + item['id']):
            result = self.client.get(path).json()
            self.assertEqual((result[0] if isinstance(result, list) else result)['lora_metadata'], snapshot)
        before = self.rows()
        with patch('backend.gallery_api.httpx.AsyncClient', side_effect=AssertionError('offline restoration')):
            restored = self.client.get('/api/artworks/' + item['id'] + '/creation-settings').json()
        self.assertEqual(restored['settings']['loras'], body['loras'])
        self.assertEqual(restored['settings']['seed'], str(2**64-1))
        self.assertEqual(restored['lora_metadata'], snapshot)
        self.assertTrue(any('與原快照不同' in message for message in restored['warnings']))
        self.assertEqual(self.rows(), before)
        self.assertEqual(json.loads(self.client.get('/api/artworks/' + item['id'] + '/workflow').text), job['workflow'])

    def test_capture_precedes_network_and_is_not_replaced_after_metadata_changes(self):
        self.prepare()
        loras.update_metadata(self.db, ENGINE, NAME, dict(version='before', sha256='a'*64))
        def changed(url):
            if url.endswith('/object_info/LoraLoader'):
                loras.update_metadata(self.db, ENGINE, NAME, dict(version='after', sha256='b'*64))
        response = self.submit(self.body(), self.remote(hook=changed))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['lora_metadata'][0]['version'], 'before')
        self.assertEqual(response.json()['lora_metadata'][0]['sha256'], 'a'*64)

    def test_ledger_deep_copies_and_refuses_snapshot_replacement(self):
        settings = main.DraftInput.model_validate(self.body()).model_dump()
        original = [lora_records.capture(dict(version='v1', sha256='a'*64), settings['loras'][0])]
        saved = copy.deepcopy(original)
        graph, job_id = workflows.build(settings), str(uuid4())
        job, _ = jobs.reserve(self.db, job_id, ENGINE, graph, settings['checkpoint'], lora_metadata=original)
        original[0]['version'] = 'changed'
        self.assertEqual(job['lora_metadata'], saved)
        repeated, fresh = jobs.reserve(self.db, job_id, ENGINE, graph, settings['checkpoint'], lora_metadata=[])
        self.assertFalse(fresh)
        self.assertEqual(repeated['lora_metadata'], saved)
        for value in (None, [], original):
            with self.assertRaises(ValueError):
                jobs.update(self.db, job_id, lora_metadata=value)
            with self.assertRaises(ValueError):
                jobs.compare_update(self.db, job, lora_metadata=value)

    def test_disabled_lora_records_known_empty_and_restores_no_active_lora(self):
        body = self.body()
        body['loras'][0]['enabled'] = False
        job = self.job(**body)
        self.assertEqual(job['lora_metadata'], [])
        item = self.artwork(job)
        self.assertEqual(item['lora_metadata'], [])
        self.assertEqual(self.client.get('/api/artworks/' + item['id'] + '/creation-settings').json()['settings']['loras'], [])

    def test_failed_preflight_restores_lora_and_keeps_failed_job_snapshot(self):
        self.prepare('sdxl', 'sd1')
        loras.update_metadata(self.db, ENGINE, NAME, dict(version='failed-v1'))
        body = self.body()
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('known mismatch')):
            response = self.client.post('/api/generate', json=body)
        self.assertEqual(response.status_code, 422, response.text)
        job_id = response.json()['detail']['job_id']
        loras.update_metadata(self.db, ENGINE, NAME, dict(version='now-v2', architecture='sdxl'))
        before = self.rows()
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no retry')):
            restored = self.client.get('/api/jobs/' + job_id + '/creation-settings')
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual(restored.json()['settings']['loras'], body['loras'])
        self.assertEqual(restored.json()['lora_metadata'][0]['version'], 'failed-v1')
        self.assertEqual(self.rows(), before)

    def test_old_records_remain_unknown_without_read_backfill(self):
        body = self.body()
        job = self.job(**body)
        job.pop('lora_metadata')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(job), 'job:' + job['id']))
        item = self.artwork(job)
        self.assertIsNone(item['lora_metadata'])
        item.pop('lora_metadata')
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE settings SET value=? WHERE key=?', (json.dumps(item), 'artwork:' + item['id']))
        before = self.rows()
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('no replay')):
            self.assertIsNone(self.client.post('/api/generate', json=body).json()['lora_metadata'])
        self.assertIsNone(self.client.get('/api/jobs/' + job['id']).json()['lora_metadata'])
        restored = self.client.get('/api/artworks/' + item['id'] + '/creation-settings').json()
        self.assertIsNone(restored['lora_metadata'])
        self.assertTrue(any('原登記版本未知' in warning for warning in restored['warnings']))
        self.assertEqual(self.rows(), before)

    def test_cached_lora_availability_and_engine_scope_are_read_only(self):
        job = self.job()
        item = self.artwork(job)
        path = '/api/artworks/' + item['id'] + '/creation-settings'
        self.assertEqual(self.client.get(path).json()['availability']['loras'][0]['status'], 'available')
        loras.merge(self.db, ENGINE, [])
        self.assertEqual(self.client.get(path).json()['availability']['loras'][0]['status'], 'missing')
        loras.mutate(self.db, ENGINE, lambda value: value.update(sync_error='offline'))
        self.client.put('/api/settings', json=dict(comfy_url='http://localhost:9000'))
        before = self.rows()
        restored = self.client.get(path).json()
        self.assertEqual(restored['availability']['loras'][0]['status'], 'unknown')
        self.assertFalse(restored['availability']['engine_matches'])
        self.assertEqual(restored['settings']['engine_url'], ENGINE)
        self.assertEqual(self.rows(), before)

    def test_reordered_graph_restores_whole_lora_template_and_rejects_partial_graphs(self):
        settings = main.DraftInput.model_validate(self.body()).model_dump()
        ids = dict(zip(workflows.ROLES, ('ckpt', 'pos', 'neg', 'latent', 'sample', 'decode', 'save'))) | dict(lora='style')
        graph = workflows.build(settings, ids)
        item = dict(workflow=graph, checkpoint=settings['checkpoint'], engine_url=ENGINE,
                    source={'node_id': 'save'}, title='reordered')
        validate = lambda data: main.DraftInput.model_validate(data).model_dump()
        result = workflows.extract(item, validate)
        self.assertEqual(result['loras'], settings['loras'])
        self.assertEqual(result['seed'], settings['seed'])
        for node, field, value in [('style', 'extra', 'lost'), ('pos', 'clip', ['ckpt', 1]),
                                   ('sample', 'model', ['ckpt', 0]), ('style', 'clip', ['ckpt', True]),
                                   ('style', 'strength_model', True), ('style', 'strength_clip', None)]:
            bad = copy.deepcopy(graph)
            bad[node]['inputs'][field] = value
            with self.assertRaises(ValueError):
                workflows.extract(item | dict(workflow=bad), validate)

    def test_unknown_metadata_stays_unknown_for_live_unregistered_name(self):
        result = self.submit(self.body(), self.remote())
        self.assertEqual(result.status_code, 200, result.text)
        item = result.json()['lora_metadata'][0]
        self.assertEqual(item['version'], '未知')
        self.assertEqual(item['architecture'], 'unknown')
        self.assertEqual(item['sha256'], '')
        self.assertEqual(item['source_url'], '')
