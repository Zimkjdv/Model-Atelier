import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from backend import main, test_submissions


class AppFactoryTests(unittest.TestCase):
    def test_two_running_apps_keep_settings_jobs_assets_and_clients_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remotes = [test_submissions.SubmissionTests.remote(self) for _ in range(2)]
            first = main.create_app(data_root=root / 'first', engine_client_factory=lambda **options: remotes[0])
            second = main.create_app(data_root=root / 'second', engine_client_factory=lambda **options: remotes[1])
            self.assertFalse((root / 'first').exists())
            self.assertFalse((root / 'second').exists())
            with TestClient(first) as a, TestClient(second) as b:
                a.put('/api/settings', json=dict(comfy_url='http://engine-a:8188'))
                self.assertEqual(b.get('/api/settings').json()['comfy_url'], 'http://127.0.0.1:8188')
                b.put('/api/settings', json=dict(comfy_url='http://engine-b:8188'))
                identifier = str(uuid4())
                for client, engine in [(a, 'http://engine-a:8188'), (b, 'http://engine-b:8188')]:
                    payload = test_submissions.SubmissionTests.payload(self) | dict(request_id=identifier, engine_url=engine)
                    response = client.post('/api/generate', json=payload)
                    self.assertEqual(response.status_code, 200, response.text[:400])
                    self.assertEqual(response.json()['engine_url'], engine)
                image = io.BytesIO()
                Image.new('RGB', (8, 8), 'red').save(image, format='PNG')
                asset = a.post('/api/assets?filename=only-a.png', content=image.getvalue()).json()
                self.assertEqual(b.get('/api/assets').json(), [])
                self.assertEqual(b.get('/api/assets/' + asset['id'] + '/image').status_code, 404)
                self.assertEqual(a.get('/api/assets/' + asset['id'] + '/image').status_code, 200)
                self.assertIsNot(first.state.context.local_environment_state, second.state.context.local_environment_state)
                for index, engine in enumerate(('http://engine-a:8188', 'http://engine-b:8188')):
                    self.assertTrue(all(call.args[0].startswith(engine) for call in remotes[index].get.await_args_list))
            with TestClient(main.create_app(data_root=root / 'first')) as restarted:
                self.assertEqual(restarted.get('/api/settings').json()['comfy_url'], 'http://engine-a:8188')
                self.assertEqual(len(restarted.get('/api/jobs').json()), 1)
                self.assertEqual(len(restarted.get('/api/assets').json()), 1)

    def test_import_has_no_database_or_data_directory_creation(self):
        script = """
from unittest.mock import patch
import fastapi, httpx, psutil
with patch('sqlite3.connect', side_effect=AssertionError('database opened at import')):
    with patch('pathlib.Path.mkdir', side_effect=AssertionError('directory created at import')):
        from backend import main
        assert callable(main.create_app)
print('import is read-only')
"""
        result = subprocess.run([sys.executable, '-c', script], capture_output=True, text=True, timeout=20,
                                cwd=Path(__file__).resolve().parents[1])
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_explicit_database_and_existing_records_need_no_rewrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'old.sqlite3'
            legacy = dict(id='old-draft', title='old', engine_url='http://old', checkpoint='', seed='18446744073709551615', updated_at='2026-10-01T00:00:00Z')
            with closing(sqlite3.connect(path)) as database, database:
                database.execute('CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                database.execute('INSERT INTO settings VALUES (?, ?)', ('draft:old-draft', json.dumps(legacy)))
            with TestClient(main.create_app(data_root=root / 'images', database=path)) as client:
                self.assertEqual(client.get('/api/drafts').json()[0]['seed'], legacy['seed'])
            with closing(sqlite3.connect(path)) as database:
                self.assertEqual(json.loads(database.execute('SELECT value FROM settings').fetchone()[0]), legacy)
