import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

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
        self.client = TestClient(main.app)

    def tearDown(self):
        self.client.close()
        self.patcher.stop()
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


if __name__ == '__main__':
    unittest.main()
