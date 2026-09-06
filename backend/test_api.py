import sqlite3
import io
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch, AsyncMock

import httpx
from PIL import Image

from fastapi.testclient import TestClient
from backend import main


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'test.sqlite3'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.patcher = patch.object(main, 'DB', self.db)
        self.patcher.start()
        self.data_patcher = patch.object(main, 'DATA', Path(self.temp.name))
        self.data_patcher.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
        self.data_patcher.stop()
        self.temp.cleanup()

    def test_settings_persist_and_invalid_url_does_not_replace(self):
        response = self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000/'})
        self.assertEqual(response.status_code, 200)
        for bad in ['file:///etc/passwd', 'http://user:pass@localhost', 'http://localhost:99999']:
            self.assertEqual(self.client.put('/api/settings', json={'comfy_url': bad}).status_code, 422)
        self.assertEqual(self.client.get('/api/settings').json()['comfy_url'], 'http://127.0.0.1:9000')

    def test_no_gpu_does_not_block_platform(self):
        with patch.object(main, 'gpu_info', return_value=([], 'unavailable')):
            result = self.client.get('/api/system')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['gpus'], [])
        self.assertGreater(result.json()['ram']['total'], 0)
        self.assertEqual(self.client.get('/api/health').status_code, 200)

    def test_gpu_unknown_memory_is_not_zero(self):
        class Result:
            returncode = 0
            stdout = '0, NVIDIA Test, 12288, [N/A], 8192, 123.4\n'
        with patch.object(main.subprocess, 'run', return_value=Result()):
            gpus, error = main.gpu_info()
        self.assertIsNone(error)
        self.assertIsNone(gpus[0]['used'])
        self.assertEqual(gpus[0]['total'], 12288 * 1024 ** 2)

    def sync(self, names=None, broken=False):
        payload = {} if names is None else {'CheckpointLoaderSimple': {'input': {'required': {'ckpt_name': [names]}}}}
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        if broken:
            remote.get.side_effect = httpx.ConnectError('offline')
        else:
            remote.get.return_value = httpx.Response(200, json=payload, request=httpx.Request('GET', 'http://test/object_info'))
        with patch.object(main.httpx, 'AsyncClient', return_value=remote):
            response = self.client.post('/api/models/sync')
        self.assertEqual(response.status_code, 200)
        return response.json()

    def target(self, name='illustration.safetensors'):
        return dict(engine_url='http://127.0.0.1:8188', name=name)

    def test_catalog_sync_preserves_metadata_and_missing_models(self):
        self.sync(['illustration.safetensors', 'illustration.safetensors', 'other.safetensors'])
        response = self.client.put('/api/models/metadata', json={**self.target(), 'version': ' v1.2 ', 'notes': '版本待驗證', 'source_url': 'https://example.com/model'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.put('/api/models/selection', json=self.target()).status_code, 200)
        result = self.sync(['other.safetensors'])
        item = next(item for item in result['models'] if item['name'] == 'illustration.safetensors')
        self.assertEqual(len(result['models']), 2)
        self.assertFalse(item['listed'])
        self.assertEqual(item['notes'], '版本待驗證')
        self.assertEqual(item['version'], 'v1.2')
        self.assertEqual(result['selected'], 'illustration.safetensors')
        self.assertEqual(self.client.put('/api/models/selection', json=self.target()).status_code, 409)
        self.assertEqual(self.client.get('/api/models').json(), result)

    def test_catalog_failure_does_not_erase_snapshot(self):
        initial = self.sync(['illustration.safetensors'])
        for result in [self.sync(broken=True), self.sync()]:
            self.assertEqual(result['models'], initial['models'])
            self.assertEqual(result['synced_at'], initial['synced_at'])
            self.assertTrue(result['sync_error'])
        self.assertIsNone(self.sync([])['sync_error'])
        self.assertFalse(self.client.get('/api/models').json()['models'][0]['listed'])

    def test_catalog_scoped_to_engine_and_rejects_stale_edits(self):
        self.sync(['illustration.safetensors'])
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:9000'})
        self.assertEqual(self.client.get('/api/models').json()['models'], [])
        self.assertEqual(self.client.put('/api/models/metadata', json=self.target()).status_code, 409)
        self.client.put('/api/settings', json={'comfy_url': 'http://127.0.0.1:8188'})
        self.assertEqual(len(self.client.get('/api/models').json()['models']), 1)

    def test_model_source_and_unknown_selection_validation(self):
        initial = self.sync(['illustration.safetensors'])
        self.assertEqual(initial['models'][0]['version'], '')
        self.assertEqual(self.client.put('/api/models/metadata', json={**self.target(), 'source_url': 'javascript:alert(1)'}).status_code, 422)
        self.assertEqual(self.client.put('/api/models/selection', json=self.target('missing')).status_code, 404)

    def draft(self, **changes):
        return dict(title='插畫草稿', prompt='森林中的小屋', engine_url='http://127.0.0.1:8188', **changes)

    def test_draft_persistence_and_conflict(self):
        created = self.client.post('/api/drafts', json=self.draft(seed='18446744073709551615'))
        self.assertEqual(created.status_code, 201)
        first = created.json()
        payload = self.draft(seed=first['seed'], revision=first['revision'])
        payload['prompt'] = '雨後的森林'
        updated = self.client.put('/api/drafts/' + first['id'], json=payload)
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()['revision'], 2)
        self.assertEqual(self.client.put('/api/drafts/' + first['id'], json=payload).status_code, 409)
        saved = self.client.get('/api/drafts').json()
        self.assertEqual(saved[0]['prompt'], '雨後的森林')
        self.assertEqual(saved[0]['seed'], '18446744073709551615')

    def test_draft_validation_and_without_model(self):
        self.assertEqual(self.client.post('/api/drafts', json=self.draft()).status_code, 201)
        for changes in [{'width': 65}, {'height': 0}, {'seed': '18446744073709551616'}, {'seed': '-1'}, {'width': 64.5}]:
            self.assertEqual(self.client.post('/api/drafts', json=self.draft(**changes)).status_code, 422)
        self.assertEqual(len(self.client.get('/api/drafts').json()), 1)
        self.assertEqual(self.client.put('/api/drafts/nonexistent', json=self.draft(revision=1)).status_code, 404)

    def test_draft_records_model_version(self):
        self.sync(['illustration.safetensors'])
        self.client.put('/api/models/metadata', json={**self.target(), 'version': '1.0'})
        saved = self.client.post('/api/drafts', json=self.draft(checkpoint='illustration.safetensors')).json()
        self.assertEqual(saved['model_version'], '1.0')
        self.client.put('/api/models/metadata', json={**self.target(), 'version': '2.0'})
        self.assertEqual(self.client.get('/api/drafts').json()[0]['model_version'], '1.0')

    def upload(self):
        stream = io.BytesIO()
        Image.new('RGB', (32, 24), '#aac8b0').save(stream, format='PNG')
        response = self.client.post('/api/assets?filename=sample.png', content=stream.getvalue())
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_asset_image_validation_and_archive_restore(self):
        self.assertEqual(self.client.post('/api/assets?filename=fake.png', content=b'not an image').status_code, 422)
        item = self.upload()
        self.assertEqual(item['width'], 32)
        image = self.client.get('/api/assets/' + item['id'] + '/image')
        self.assertEqual(image.headers['content-type'], 'image/png')
        self.assertEqual(Image.open(io.BytesIO(image.content)).size, (32, 24))
        for archived in (True, False):
            response = self.client.put('/api/assets/' + item['id'], json={'title': '改名', 'archived': archived})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['archived'], archived)

    def test_referenced_asset_cannot_be_archived(self):
        item = self.upload()
        draft = self.client.post('/api/drafts', json=self.draft(reference_ids=[item['id']])).json()
        endpoint = '/api/assets/' + item['id']
        self.assertEqual(self.client.put(endpoint, json={'title': item['title'], 'archived': True}).status_code, 409)
        update = self.draft(reference_ids=[], revision=draft['revision'])
        self.assertEqual(self.client.put('/api/drafts/' + draft['id'], json=update).status_code, 200)
        self.assertEqual(self.client.put(endpoint, json={'title': item['title'], 'archived': True}).status_code, 200)
        self.assertEqual(self.client.post('/api/drafts', json=self.draft(reference_ids=[item['id']])).status_code, 409)

    def test_asset_limits_and_missing_reference(self):
        with patch.object(main.assets, 'MAX_BYTES', 5):
            self.assertEqual(self.client.post('/api/assets', content=b'123456').status_code, 413)
        self.assertEqual(self.client.post('/api/drafts', json=self.draft(reference_ids=['00000000-0000-0000-0000-000000000000'])).status_code, 409)
        self.assertEqual(self.client.get('/api/assets/not-a-uuid/image').status_code, 422)


if __name__ == '__main__':
    unittest.main()
