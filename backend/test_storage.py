import os
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
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
        with (
            patch.object(storage, 'volume_identity', return_value=('same-volume', 'C:\\')),
            patch.object(storage.shutil, 'disk_usage', return_value=Usage(100, 60, 40)) as disk,
        ):
            result = storage.inventory([('models', self.a), ('assets', self.b), ('output', self.a)])
        self.assertEqual(disk.call_count, 1)
        self.assertEqual(result['totals'], dict(total=100, free=40, volume_count=1, partial=False))
        self.assertEqual(len(result['directories']), 3)

    def test_distinct_volumes_sum_once_each(self):
        with (
            patch.object(storage, 'volume_identity', side_effect=lambda p: (str(p), str(p))),
            patch.object(storage.shutil, 'disk_usage', return_value=Usage(100, 60, 40)),
        ):
            result = storage.inventory([('models', self.a), ('assets', self.b)])
        self.assertEqual(result['totals']['total'], 200)
        self.assertEqual(result['totals']['volume_count'], 2)

    def test_missing_unreadable_and_relative_are_unknown_not_zero(self):
        with patch.object(storage, 'volume_identity', side_effect=PermissionError):
            result = storage.inventory(
                [
                    ('missing', self.root / 'missing'),
                    ('denied', self.a),
                    ('relative', Path('relative')),
                ]
            )
        self.assertTrue(result['totals']['partial'])
        self.assertIsNone(result['totals']['free'])
        self.assertEqual(result['directories'][0]['status'], 'missing')
        self.assertFalse((self.root / 'missing').exists())

    def test_invalid_capacity_is_unknown_and_not_retried_per_directory(self):
        for usage in (
            Usage(100, 1, 101),
            Usage(100, 80, 40),
            Usage(100, -1, 20),
            Usage(0, 0, 0),
            Usage(True, 0, 0),
        ):
            with (
                patch.object(storage, 'volume_identity', return_value=('v', 'root')),
                patch.object(storage.shutil, 'disk_usage', return_value=usage) as disk,
            ):
                result = storage.inventory([('a', self.a), ('b', self.b)])
            self.assertIsNone(result['totals']['total'])
            self.assertTrue(result['totals']['partial'])
            self.assertEqual(disk.call_count, 1)

    def test_invalid_registry_preserves_fixed_directories(self):
        with patch.object(model_paths, 'read', side_effect=ValueError):
            result = storage.report(
                self.root, self.root, self.root / 'absent.sqlite', 'http://remote:8188'
            )
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
        with (
            patch.object(main.httpx, 'AsyncClient', side_effect=AssertionError('no network')),
            patch.object(self.host, 'gpu_info', side_effect=AssertionError('no GPU')),
        ):
            result = self.client.get('/api/storage')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()['scope'], 'platform_and_managed_local_paths')
        self.assertEqual(self.db.read_bytes(), original)


class LocalFolderTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def local_client(self):
        return TestClient(self.app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 23456))

    def body(self, identifier='data', path=None):
        return dict(directory_id=identifier, expected_path=str(path or self.host.DATA.resolve()))

    def test_open_known_directory_once_without_shell_or_data_changes(self):
        before = self.db.read_bytes()
        with (
            self.local_client() as client,
            patch.object(storage, 'folder_open_supported', return_value=True),
            patch.object(storage.os, 'startfile', create=True) as opener,
        ):
            report = client.get('/api/storage').json()
            entry = next(item for item in report['directories'] if item['id'] == 'data')
            self.assertTrue(entry['can_open'])
            response = client.post(
                '/api/storage/open-directory',
                json=self.body(),
                headers={'Origin': 'http://127.0.0.1:8000'},
            )
        self.assertEqual(response.status_code, 200)
        opener.assert_called_once_with(str(self.host.DATA.resolve()), 'open')
        self.assertEqual(self.db.read_bytes(), before)

    def test_extra_directory_identity_survives_reordering_and_rejects_removed_entries(self):
        first = self.host.DATA / 'models with spaces & unicode'
        second = self.host.DATA / 'other models'
        first.mkdir()
        second.mkdir()
        model_paths.save(self.db, self.host.ROOT, [str(first), str(second)], 0)
        with (
            self.local_client() as client,
            patch.object(storage, 'folder_open_supported', return_value=True),
            patch.object(storage.os, 'startfile', create=True) as opener,
        ):
            entry = next(
                item
                for item in client.get('/api/storage').json()['directories']
                if item['path'] == str(first.resolve())
            )
            model_paths.save(self.db, self.host.ROOT, [str(second), str(first)], 1)
            response = client.post(
                '/api/storage/open-directory', json=self.body(entry['id'], first.resolve())
            )
            self.assertEqual(response.status_code, 200)
            opener.assert_called_once_with(str(first.resolve()), 'open')
            model_paths.save(self.db, self.host.ROOT, [str(second)], 2)
            self.assertEqual(
                client.post(
                    '/api/storage/open-directory', json=self.body(entry['id'], first.resolve())
                ).status_code,
                404,
            )
            self.assertEqual(opener.call_count, 1)

    def test_arbitrary_paths_stale_paths_missing_directories_and_files_never_open(self):
        with (
            self.local_client() as client,
            patch.object(storage, 'folder_open_supported', return_value=True),
            patch.object(storage.os, 'startfile', create=True) as opener,
        ):
            for body, expected in [
                (self.body('../../Windows'), 404),
                (self.body(path=self.host.ROOT), 409),
                (self.body() | {'path': str(self.host.ROOT)}, 422),
                (self.body('assets', self.host.DATA / 'assets'), 409),
            ]:
                self.assertEqual(
                    client.post('/api/storage/open-directory', json=body).status_code, expected
                )
            missing = self.host.DATA / 'assets'
            self.assertFalse(missing.exists())
            missing.write_text('not a directory', encoding='utf-8')
            self.assertEqual(
                client.post(
                    '/api/storage/open-directory', json=self.body('assets', missing)
                ).status_code,
                409,
            )
            entry = next(
                item
                for item in client.get('/api/storage').json()['directories']
                if item['id'] == 'assets'
            )
            self.assertFalse(entry['can_open'])
            opener.assert_not_called()

    def test_remote_cross_origin_and_rebound_host_requests_never_open(self):
        with (
            self.local_client() as client,
            patch.object(storage, 'folder_open_supported', return_value=True),
            patch.object(storage.os, 'startfile', create=True) as opener,
        ):
            for headers in (
                {'Origin': 'https://example.com'},
                {'Origin': 'null'},
                {'Origin': 'http://127.0.0.1:8001'},
                {'Host': 'example.com'},
                {'Sec-Fetch-Site': 'cross-site'},
            ):
                self.assertEqual(
                    client.post(
                        '/api/storage/open-directory', json=self.body(), headers=headers
                    ).status_code,
                    403,
                )
            with TestClient(
                self.app, base_url='http://127.0.0.1:8000', client=('192.168.1.2', 23456)
            ) as remote:
                self.assertEqual(
                    remote.post('/api/storage/open-directory', json=self.body()).status_code, 403
                )
            opener.assert_not_called()

    def test_unsupported_platform_and_explorer_failure_are_explicit_without_retry(self):
        with (
            self.local_client() as client,
            patch.object(storage, 'folder_open_supported', return_value=False),
        ):
            self.assertEqual(
                client.post('/api/storage/open-directory', json=self.body()).status_code, 501
            )
            self.assertFalse(client.get('/api/storage').json()['directories'][0]['can_open'])
        with (
            self.local_client() as client,
            patch.object(storage, 'folder_open_supported', return_value=True),
            patch.object(
                storage.os, 'startfile', create=True, side_effect=OSError('PRIVATE_TRACE')
            ) as opener,
        ):
            response = client.post('/api/storage/open-directory', json=self.body())
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('PRIVATE_TRACE', response.text)
            self.assertEqual(opener.call_count, 1)

    def test_network_directories_are_rejected_before_filesystem_access(self):
        with patch.object(
            storage.os, 'scandir', side_effect=AssertionError('must not visit network')
        ):
            result = storage.inventory([('network', Path('//server/share/weights'))])
        self.assertIsNone(result['directories'][0]['resolved_path'])
        self.assertTrue(result['totals']['partial'])


if __name__ == '__main__':
    unittest.main()
