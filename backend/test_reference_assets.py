import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
from backend import main, assets


class ReferenceAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.db = self.folder / 'test.sqlite3'
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.db_patch = patch.object(main, 'DB', self.db)
        self.data_patch = patch.object(main, 'DATA', self.folder)
        self.db_patch.start(); self.data_patch.start()
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close(); self.db_patch.stop(); self.data_patch.stop(); self.temp.cleanup()

    def create(self):
        data = io.BytesIO()
        Image.new('RGB', (80, 64), 'green').save(data, format='PNG')
        return self.client.post('/api/assets?filename=reference.png', content=data.getvalue()).json()

    def put(self, item, **changes):
        return self.client.put('/api/assets/' + item['id'], json=dict(title=item['title'], revision=item['revision']) | changes)

    def record(self, key, value):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('INSERT OR REPLACE INTO settings VALUES (?, ?)', (key, json.dumps(value)))

    def test_purpose_filter_metadata_and_revision_conflict(self):
        first = self.create()
        self.assertEqual(first['purpose'], 'unspecified')
        self.assertEqual(first['preprocessing']['version'], 1)
        self.assertEqual(first['preprocessing']['source_size'], [80, 64])
        second = self.put(first, purpose='composition').json()
        self.assertEqual(second['purpose'], 'composition')
        self.assertEqual(second['revision'], 2)
        self.assertEqual(self.put(first, purpose='style').status_code, 409)
        self.assertEqual(self.client.get('/api/assets').json()[0]['purpose'], 'composition')
        self.assertEqual(self.put(second, purpose='executable').status_code, 422)

    def test_legacy_defaults_do_not_rewrite_or_invent_provenance(self):
        item = self.create()
        for key in ('purpose', 'revision', 'preprocessing'):
            item.pop(key)
        self.record('asset:' + item['id'], item)
        displayed = self.client.get('/api/assets').json()[0]
        self.assertEqual(displayed['revision'], 0)
        self.assertEqual(displayed['purpose'], 'unspecified')
        self.assertIsNone(displayed['preprocessing'])
        with closing(sqlite3.connect(self.db)) as db:
            stored = json.loads(db.execute('SELECT value FROM settings WHERE key=?', ('asset:' + item['id'],)).fetchone()[0])
        self.assertEqual(stored, item)

    def test_task_and_artwork_references_prevent_archive_but_allow_rename(self):
        for group in ('job', 'artwork'):
            with self.subTest(group=group):
                item = self.create()
                record_id = str(uuid4())
                self.record(group + ':' + record_id, dict(id=record_id, reference_metadata=[dict(id=item['id'])]))
                response = self.put(item, archived=True)
                self.assertEqual(response.status_code, 409)
                usage = self.client.get('/api/assets/' + item['id'] + '/usage').json()
                self.assertEqual(usage['jobs' if group == 'job' else 'artworks'], [record_id])
                renamed = self.put(item, title='新名稱', purpose='style')
                self.assertEqual(renamed.status_code, 200)
                self.assertFalse(renamed.json()['archived'])

    def test_draft_reference_archive_and_recover(self):
        item = self.create()
        draft = self.client.post('/api/drafts', json=dict(title='參考草稿', engine_url='http://127.0.0.1:8188', reference_ids=[item['id']])).json()
        self.assertEqual(self.put(item, archived=True).status_code, 409)
        self.assertEqual(self.client.get('/api/assets/' + item['id'] + '/usage').json()['drafts'], [draft['id']])
        draft['reference_ids'] = []
        self.assertEqual(self.client.put('/api/drafts/' + draft['id'], json=draft).status_code, 200)
        archived = self.put(item, archived=True).json()
        self.assertTrue(archived['archived'])
        self.assertFalse(self.put(archived, archived=False).json()['archived'])

    def test_unknown_usage_and_explicit_capabilities(self):
        self.assertEqual(self.client.get('/api/assets/' + str(uuid4()) + '/usage').status_code, 404)
        values = self.client.get('/api/reference-workflows').json()
        self.assertEqual(len({item['id'] for item in values}), len(values))
        self.assertTrue(values[0]['implemented'])
        self.assertFalse(next(item for item in values if item['id'] == 'style-reference')['implemented'])
        self.assertEqual(set(assets.PURPOSES), {'unspecified', 'style', 'character', 'composition'})
