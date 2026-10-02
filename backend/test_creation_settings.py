import copy
import io
import json
import sqlite3
import unittest
from contextlib import closing
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from backend import catalog, drafts, gallery, jobs, main, test_api, test_submissions, workflows


class CreationSettingsTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def settings(self, **changes):
        value = dict(title='作品再創作', prompt='a forest', negative_prompt='blurry',
                     engine_url='http://127.0.0.1:8188', checkpoint='sample.safetensors',
                     width=832, height=1216, seed=str(2**64 - 1), steps=37, cfg=5.55,
                     sampler_name='dpmpp_2m', scheduler='karras', denoise=0.123)
        return main.DraftInput(**(value | changes)).model_dump(mode='json', exclude={'revision'})

    def artwork(self, workflow=None, version='v1', node_id='7'):
        workflow = workflow or workflows.build(self.settings())
        job_id = str(uuid4())
        job, _ = jobs.reserve(self.db, job_id, 'http://127.0.0.1:8188', workflow, 'sample.safetensors', version)
        source = dict(node_id=node_id, filename='sample.png', subfolder='', type='output')
        raw = io.BytesIO()
        # Deliberately differs from the latent dimensions to catch image-size guesses.
        Image.new('RGB', (800, 600), '#718d76').save(raw, 'PNG')
        item, _ = gallery.save(self.db, self.db.parent / 'artworks', job, source, raw.getvalue())
        return item

    def restore(self, item):
        return self.client.get('/api/artworks/' + item['id'] + '/creation-settings')

    def test_restore_exact_parameters_seed_and_original_version_offline(self):
        item = self.artwork()
        snapshot = catalog.merge(self.db, item['engine_url'], [item['checkpoint']])
        snapshot['models'][0]['version'] = 'v2'
        catalog.write(self.db, snapshot)
        with closing(sqlite3.connect(self.db)) as db:
            before = db.execute('SELECT key, value FROM settings ORDER BY key').fetchall()
        with patch('backend.gallery_api.httpx.AsyncClient', side_effect=AssertionError('must remain offline')):
            response = self.restore(item)
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual(result['settings'], self.settings(title='sample.png'))
        self.assertEqual(result['settings']['seed'], '18446744073709551615')
        self.assertEqual(result['model_version'], 'v1')
        self.assertTrue(any('模型版本' in warning for warning in result['warnings']))
        self.assertEqual(result['availability']['checkpoint_status'], 'available')
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(before, db.execute('SELECT key, value FROM settings ORDER BY key').fetchall())

    def test_restore_reordered_node_ids_and_missing_local_image(self):
        ids = dict(zip(workflows.ROLES, ('ckpt', 'pos', 'neg', 'latent', 'sample', 'decode', 'save')))
        graph = workflows.build(self.settings(), ids)
        graph['pos']['_meta'] = {'title': 'Positive prompt'}
        item = self.artwork(graph, node_id='save')
        (self.db.parent / 'artworks' / (item['id'] + '.png')).unlink()
        result = self.restore(item)
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['settings']['width'], 832)
        self.assertEqual(result.json()['settings']['prompt'], 'a forest')

    def test_long_output_filename_becomes_valid_draft_title(self):
        item = self.artwork()
        item['title'] = 'x' * 180 + '.png'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE settings SET value=? WHERE key=?',
                       (json.dumps(item), 'artwork:' + item['id']))
        response = self.restore(item)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['settings']['title'], 'x' * 100)
        self.assertEqual(gallery.get(self.db, item['id'])['title'], item['title'])

    def test_cached_availability_is_scoped_to_original_engine(self):
        item = self.artwork(version=None)
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        catalog.merge(self.db, 'http://127.0.0.1:9000', [item['checkpoint']])
        result = self.restore(item).json()
        self.assertEqual(result['settings']['engine_url'], item['engine_url'])
        self.assertEqual(result['model_version'], '未知')
        self.assertFalse(result['availability']['engine_matches'])
        self.assertEqual(result['availability']['checkpoint_status'], 'unknown')
        catalog.merge(self.db, item['engine_url'], [])
        result = self.restore(item).json()
        self.assertEqual(result['availability']['checkpoint_status'], 'missing')
        self.assertTrue(any('原 checkpoint' in warning for warning in result['warnings']))
        value = catalog.read(self.db, item['engine_url'])
        value['sync_error'] = 'offline'
        catalog.write(self.db, value)
        self.assertEqual(self.restore(item).json()['availability']['checkpoint_status'], 'unknown')

    def test_unsupported_or_malformed_graph_cannot_be_partially_restored(self):
        original = workflows.build(self.settings())
        graphs = []
        extra = copy.deepcopy(original)
        extra['8'] = {'class_type': 'CustomNode', 'inputs': {}}
        graphs.append(extra)
        for node, field, value in [('5', 'denoise', None), ('4', 'batch_size', 2), ('4', 'width', 65),
                                    ('5', 'seed', True), ('5', 'steps', '37'), ('5', 'cfg', True),
                                    ('5', 'model', ['1', True]), ('2', 'clip', ['1', 0]),
                                    ('1', 'ckpt_name', 'other.safetensors'), ('5', 'extra_config', 1)]:
            graph = copy.deepcopy(original)
            if value is None:
                graph[node]['inputs'].pop(field)
            else:
                graph[node]['inputs'][field] = value
            graphs.append(graph)
        for graph in graphs:
            with self.subTest(graph=graph):
                response = self.restore(self.artwork(graph))
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn('無法完整還原', response.json()['detail'])
        self.assertEqual(self.restore(dict(id=str(uuid4()))).status_code, 404)

    def test_old_drafts_receive_defaults_without_database_rewrite(self):
        old = self.settings()
        for name in ('negative_prompt', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'):
            old.pop(name)
        original = drafts.save(self.db, old)
        restored = self.client.get('/api/drafts').json()[0]
        self.assertEqual({key: restored[key] for key in ('negative_prompt', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise')},
                         dict(negative_prompt='', steps=20, cfg=7, sampler_name='euler', scheduler='normal', denoise=1))
        self.assertEqual(drafts.list_all(self.db)[0], original)

    def test_generation_parameters_are_saved_and_forwarded(self):
        body = self.settings(checkpoint='test.safetensors')
        draft = self.client.post('/api/drafts', json=body)
        self.assertEqual(draft.status_code, 201, draft.text)
        for name in ('negative_prompt', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise'):
            self.assertEqual(draft.json()[name], body[name])
        remote = test_submissions.SubmissionTests.remote(self)
        with patch('backend.submissions.httpx.AsyncClient', return_value=remote):
            response = self.client.post('/api/generate', json=body | {'request_id': str(uuid4())})
        self.assertEqual(response.status_code, 200, response.text)
        submitted = remote.post.call_args.kwargs['json']['prompt']
        self.assertEqual(submitted, workflows.build(body))
        self.assertEqual(submitted['3']['inputs']['text'], 'blurry')

    def test_invalid_parameters_fail_before_network_or_persistence(self):
        body = self.settings()
        bad = [{'steps': 0}, {'steps': 151}, {'steps': 1.5}, {'cfg': -1}, {'cfg': 31}, {'cfg': '7'},
               {'denoise': -0.01}, {'denoise': 1.01}, {'denoise': True}, {'sampler_name': ''},
               {'sampler_name': 'euler/../x'}, {'scheduler': 'normal with spaces'}, {'negative_prompt': 'x' * 20001}]
        with patch('backend.submissions.httpx.AsyncClient', side_effect=AssertionError('unexpected network')):
            for changes in bad:
                self.assertEqual(self.client.post('/api/drafts', json=body | changes).status_code, 422, changes)
                self.assertEqual(self.client.post('/api/generate', json=body | changes | {'request_id': str(uuid4())}).status_code, 422, changes)
            for field, literal in [('cfg', 'NaN'), ('cfg', 'Infinity'), ('denoise', '-Infinity')]:
                content = json.dumps(body | {'request_id': str(uuid4())}).replace('"' + field + '": ' + str(body[field]), '"' + field + '": ' + literal)
                self.assertEqual(self.client.post('/api/generate', content=content, headers={'Content-Type': 'application/json'}).status_code, 422)
        self.assertEqual(jobs.list_all(self.db), [])
        self.assertEqual(drafts.list_all(self.db), [])
