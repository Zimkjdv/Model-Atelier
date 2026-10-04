import json
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient

from backend import catalog, loras, main, test_api

ENGINE = 'http://127.0.0.1:8188'
OTHER = 'http://127.0.0.1:9000'
NAME = 'styles/example.safetensors'


class LoraTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown

    def sync(self, names=None, *, payload=None, failure=None, during=None):
        remote = AsyncMock()
        remote.__aenter__.return_value = remote
        def response(url):
            self.assertEqual(url, main.engine_url() + '/object_info/LoraLoader')
            if during:
                during()
            if failure:
                raise failure
            return httpx.Response(200, json=payload if payload is not None else {
                'LoraLoader': {'input': {'required': {'lora_name': [names]}}}}, request=httpx.Request('GET', url))
        remote.get.side_effect = response
        with patch('backend.loras.httpx.AsyncClient', return_value=remote) as client:
            result = self.client.post('/api/loras/sync', json={'engine_url': main.engine_url()})
        client.assert_called_once_with(timeout=10, trust_env=False)
        remote.post.assert_not_called()
        return result

    def register(self, **changes):
        return self.client.put('/api/loras/metadata', json=dict(engine_url=ENGINE, name=NAME) | changes)

    def rows(self):
        with closing(sqlite3.connect(self.db)) as db:
            return db.execute('SELECT key, value FROM settings ORDER BY key').fetchall()

    def test_empty_read_is_read_only_and_does_not_contact_engine_or_gpu(self):
        before = self.rows()
        with (patch('backend.loras.httpx.AsyncClient', side_effect=AssertionError('no engine access')),
              patch.object(main, 'gpu_info', side_effect=AssertionError('no GPU access'))):
            result = self.client.get('/api/loras')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json(), dict(engine_url=ENGINE, loras=[], synced_at=None, sync_error=None))
        self.assertEqual(before, self.rows())

    def test_registration_persists_preserves_metadata_and_keeps_checkpoint_catalog_separate(self):
        catalog.merge(self.db, ENGINE, [NAME])
        original = catalog.read(self.db, ENGINE)
        result = self.sync([NAME, NAME, 'other.safetensors'])
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(len(result.json()['loras']), 2)
        item = next(item for item in result.json()['loras'] if item['name'] == NAME)
        self.assertEqual(item['architecture'], 'unknown')
        self.assertEqual(item['version'], '')
        self.assertEqual(item['origin'], 'user_registered')
        value = self.register(version=' v2 ', architecture='sdxl', sha256='A' * 64,
                              size_bytes=12345, source_url='https://example.org/lora/',
                              license_name=' Example ', license_url='https://example.org/license', notes='備註')
        self.assertEqual(value.status_code, 200, value.text)
        saved = next(item for item in value.json()['loras'] if item['name'] == NAME)
        self.assertEqual(saved['version'], 'v2')
        self.assertEqual(saved['sha256'], 'a' * 64)
        self.assertEqual(saved['license_name'], 'Example')
        self.assertTrue(saved['metadata_updated_at'])
        result = self.sync(['other.safetensors']).json()
        missing = next(item for item in result['loras'] if item['name'] == NAME)
        self.assertEqual(missing, saved | {'listed': False})
        self.client.close()
        self.client = TestClient(main.app)
        self.assertEqual(self.client.get('/api/loras').json(), result)
        self.assertEqual(catalog.read(self.db, ENGINE), original)

    def test_partial_updates_and_explicit_clearing_do_not_overwrite_omitted_fields(self):
        self.sync([NAME])
        first = self.register(version='1', notes='original', architecture='sdxl', size_bytes=100).json()['loras'][0]
        second = self.register(version='2').json()['loras'][0]
        self.assertEqual(second['notes'], first['notes'])
        self.assertEqual(second['architecture'], 'sdxl')
        cleared = self.register(architecture=None, notes=None, size_bytes=None).json()['loras'][0]
        self.assertEqual(cleared['architecture'], 'unknown')
        self.assertEqual(cleared['notes'], '')
        self.assertIsNone(cleared['size_bytes'])
        self.assertEqual(cleared['version'], '2')
        self.assertEqual(self.register().json()['loras'][0], cleared)

    def test_failed_or_invalid_sync_preserves_successful_snapshot_and_safe_error(self):
        before = self.sync([NAME]).json()
        for failure, payload in [(httpx.ConnectError('private credentials'), None),
                                 (None, {}), (None, {'LoraLoader': {'input': {'required': {'lora_name': [[None]]}}}})]:
            result = self.sync(payload=payload, failure=failure).json()
            self.assertEqual(result['loras'], before['loras'])
            self.assertEqual(result['synced_at'], before['synced_at'])
            self.assertTrue(result['sync_error'])
            self.assertNotIn('private credentials', result['sync_error'])
        result = self.sync([]).json()
        self.assertIsNone(result['sync_error'])
        self.assertFalse(result['loras'][0]['listed'])

    def test_scope_rejects_stale_edits_and_sync_then_restores_original_engine_records(self):
        self.sync([NAME])
        self.register(version='original')
        self.client.put('/api/settings', json={'comfy_url': OTHER})
        self.assertEqual(self.client.get('/api/loras').json()['loras'], [])
        self.assertEqual(self.register(version='stale').status_code, 409)
        with patch('backend.loras.httpx.AsyncClient', side_effect=AssertionError('stale sync must not access engine')):
            result = self.client.post('/api/loras/sync', json={'engine_url': ENGINE})
        self.assertEqual(result.status_code, 409)
        self.sync([NAME])
        self.client.put('/api/settings', json={'comfy_url': ENGINE})
        self.assertEqual(self.client.get('/api/loras').json()['loras'][0]['version'], 'original')

    def test_engine_change_during_fetch_discards_reply_instead_of_persisting_to_wrong_engine(self):
        for failure in [None, httpx.ConnectError('offline')]:
            self.client.put('/api/settings', json={'comfy_url': ENGINE})
            before = loras.read(self.db, ENGINE)
            result = self.sync([NAME], failure=failure, during=lambda: self.client.put('/api/settings', json={'comfy_url': OTHER}))
            self.assertEqual(result.status_code, 409, result.text)
            self.assertEqual(loras.read(self.db, ENGINE), before)
            self.assertEqual(loras.read(self.db, OTHER)['loras'], [])

    def test_invalid_metadata_and_unknown_names_do_not_change_storage(self):
        self.sync([NAME])
        before = self.rows()
        for changes in [dict(source_url='javascript:alert(1)'), dict(source_url='http://u:p@localhost'),
                        dict(license_url='file:///test'), dict(architecture='SDXL'), dict(sha256='abcd'),
                        dict(size_bytes=True), dict(size_bytes=1.2), dict(size_bytes=0), dict(size_bytes=2**53),
                        dict(version='x' * 101), dict(name=' '), dict(origin='verified_file'),
                        dict(metadata_updated_at='2000'), dict(engine_url='file:///test')]:
            with self.subTest(changes=changes):
                self.assertEqual(self.register(**changes).status_code, 422)
                self.assertEqual(self.rows(), before)
        self.assertEqual(self.register(name='missing').status_code, 404)
        self.assertEqual(self.rows(), before)

    def test_name_parser_rejects_malformed_input_without_guessing_architecture(self):
        for names in [None, 'file', [True], [' '], ['a' * 2049], [dict(name='model')]]:
            with self.subTest(names=names), self.assertRaises(ValueError):
                loras.names_from({'LoraLoader': {'input': {'required': {'lora_name': [names]}}}})
        self.sync(['sdxl-pony-flux-v6.safetensors'])
        self.assertEqual(self.client.get('/api/loras').json()['loras'][0]['architecture'], 'unknown')

    def test_concurrent_database_sync_and_metadata_edit_do_not_lose_registered_fields(self):
        loras.merge(self.db, ENGINE, [NAME])
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(loras.merge, self.db, ENGINE, [NAME, 'new']),
                       pool.submit(loras.update_metadata, self.db, ENGINE, NAME, dict(version='kept', architecture='sdxl'))]
            for future in futures:
                future.result()
        result = loras.read(self.db, ENGINE)
        self.assertEqual({item['name'] for item in result['loras']}, {NAME, 'new'})
        item = next(item for item in result['loras'] if item['name'] == NAME)
        self.assertEqual(item['version'], 'kept')
        self.assertEqual(item['architecture'], 'sdxl')


if __name__ == '__main__':
    unittest.main()
