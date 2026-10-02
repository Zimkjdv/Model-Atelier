import os
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch
from backend import main, model_paths, storage, test_api

Usage = namedtuple('Usage', 'total used free')


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.a = self.root / 'a'
        self.b = self.root / 'b'
        self.a.mkdir()
        self.b.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_volume_aliases_are_counted_and_queried_once(self):
        with (patch.object(storage, 'volume_identity', return_value=('same-volume', 'C:\\')),
              patch.object(storage.shutil, 'disk_usage', return_value=Usage(100, 60, 40)) as disk):
            result = storage.inventory([('models', self.a), ('assets', self.b), ('output', self.a)])
        self.assertEqual(disk.call_count, 1)
        self.assertEqual(result['totals'], dict(total=100, free=40, volume_count=1, partial=False))
        self.assertEqual(len(result['directories']), 3)

    def test_distinct_volumes_sum_once_each(self):
        with (patch.object(storage, 'volume_identity', side_effect=lambda p: (str(p), str(p))),
              patch.object(storage.shutil, 'disk_usage', return_value=Usage(100, 60, 40))):
            result = storage.inventory([('models', self.a), ('assets', self.b)])
        self.assertEqual(result['totals']['total'], 200)
        self.assertEqual(result['totals']['volume_count'], 2)

    def test_missing_unreadable_and_relative_are_unknown_not_zero(self):
        with patch.object(storage, 'volume_identity', side_effect=PermissionError):
            result = storage.inventory([('missing', self.root / 'missing'), ('denied', self.a), ('relative', Path('relative'))])
        self.assertTrue(result['totals']['partial'])
        self.assertIsNone(result['totals']['free'])
        self.assertEqual(result['directories'][0]['status'], 'missing')
        self.assertFalse((self.root / 'missing').exists())

    def test_invalid_capacity_is_unknown_and_not_retried_per_directory(self):
        for usage in (Usage(100, 1, 101), Usage(100, 80, 40), Usage(100, -1, 20), Usage(0, 0, 0), Usage(True, 0, 0)):
            with (patch.object(storage, 'volume_identity', return_value=('v', 'root')),
                  patch.object(storage.shutil, 'disk_usage', return_value=usage) as disk):
                result = storage.inventory([('a', self.a), ('b', self.b)])
            self.assertIsNone(result['totals']['total'])
            self.assertTrue(result['totals']['partial'])
            self.assertEqual(disk.call_count, 1)

    def test_invalid_registry_preserves_fixed_directories(self):
        with patch.object(model_paths, 'read', side_effect=ValueError):
            result = storage.report(self.root, self.root, self.root / 'absent.sqlite', 'http://remote:8188')
        self.assertEqual(len(result['directories']), 5)
        self.assertEqual(result['scope'], 'platform_and_managed_local_paths')
        self.assertTrue(result['totals']['partial'])
        self.assertFalse((self.root / 'absent.sqlite').exists())

    def test_real_volume_identity_same_parent_and_child(self):
        identity, label = storage.volume_identity(self.root)
        self.assertEqual(storage.volume_identity(self.a)[0], identity)
        self.assertTrue(label)
        if os.name == 'nt':
            self.assertTrue(identity.startswith('\\\\?\\volume{'))


class StorageApiTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def test_readonly_api_without_gpu_or_engine_calls(self):
        original = self.db.read_bytes()
        with (patch.object(main.httpx, 'AsyncClient', side_effect=AssertionError('no network')),
              patch.object(main, 'gpu_info', side_effect=AssertionError('no GPU'))):
            result = self.client.get('/api/storage')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['scope'], 'platform_and_managed_local_paths')
        self.assertEqual(self.db.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
