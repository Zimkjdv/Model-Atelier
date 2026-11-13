import os
from pathlib import Path
import sqlite3
import tempfile
from threading import Event
from time import monotonic, sleep
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main, model_paths, storage, storage_categories as categories
from backend.deployment_profile import Profile


class StorageCategoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.data = self.root / 'data'
        self.models = self.root / 'runtime' / 'ComfyUI' / 'models'
        self.artworks = self.data / 'artworks'
        self.models.mkdir(parents=True)
        self.artworks.mkdir(parents=True)

    def client(self, **options):
        app = main.create_app(root=self.root, data_root=self.data, **options)
        return TestClient(app, base_url='http://127.0.0.1:8000', client=('127.0.0.1', 23456))

    def wait(self, client, identifier, status):
        deadline = monotonic() + 5
        while monotonic() < deadline:
            result = client.get('/api/storage/scans/' + identifier)
            self.assertEqual(result.status_code, 200)
            report = result.json()
            if report['scan']['status'] == status:
                return report
            if report['scan']['status'] not in categories.ACTIVE:
                self.fail(report)
            sleep(0.02)
        self.fail('scan did not reach ' + status)

    def start(self, client):
        response = client.post('/api/storage/scans', json={})
        self.assertEqual(response.status_code, 202)
        return response.json()['scan']['id']

    def direct(self, roots=None):
        return categories.measure(
            dict(
                unavailable=[],
                roots=[
                    dict(category=name, path=str(path), absent_is_empty=name == 'artworks')
                    for name, path in (
                        roots or [('models', self.models), ('artworks', self.artworks)]
                    )
                ],
            ),
            Event(),
            lambda _: None,
        )

    def test_registered_overlap_and_hardlinks_count_once_using_logical_bytes(self):
        extra = self.models / 'loras'
        extra.mkdir()
        (extra / 'model.bin').write_bytes(b'model')
        os.link(extra / 'model.bin', self.models / 'hardlink.bin')
        with (self.artworks / 'logical.bin').open('wb') as stream:
            stream.truncate(100_000_000)
        with self.client() as client:
            db = self.data / 'atelier.sqlite3'
            model_paths.save(db, self.root, [str(extra)], 0)
            before = db.read_bytes()
            self.assertIsNone(client.get('/api/storage/categories').json()['scan'])
            self.assertEqual(db.read_bytes(), before)
            self.assertEqual(
                client.post('/api/storage/scans', json={'path': str(self.root)}).status_code, 422
            )
            report = self.wait(client, self.start(client), 'completed')
            scan = report['scan']
            self.assertEqual(scan['metric'], 'logical_bytes')
            self.assertEqual(scan['visited'], 4)
            self.assertEqual(scan['categories']['models']['bytes'], 5)
            self.assertEqual(scan['categories']['artworks']['bytes'], 100_000_000)
            self.assertIsNone(scan['other_bytes'])
            self.assertEqual(len(scan['volumes']), 1)
            self.assertEqual(report['known']['models']['volumes'][0]['bytes'], 5)
            self.assertIsNone(report['known']['models']['stale_reason'])
            model_paths.save(db, self.root, [], 1)
            stale = client.get('/api/storage/categories').json()
            self.assertIn('設定已變更', stale['known']['models']['stale_reason'])
            self.assertEqual(stale['last_completed']['categories']['models']['bytes'], 5)
            with patch.object(categories, 'TTL_SECONDS', 0):
                self.wait(client, self.start(client), 'completed')
                expired = client.get('/api/storage/categories').json()
                self.assertIn('超過一小時', expired['last_completed']['stale_reason'])

    def test_cross_category_links_and_empty_overlaps_are_incomplete(self):
        (self.models / 'shared.bin').write_bytes(b'shared')
        (self.models / 'private.bin').write_bytes(b'private')
        os.link(self.models / 'shared.bin', self.artworks / 'shared.bin')
        result = self.direct()
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['categories']['models']['observed_bytes'], 7)
        self.assertEqual(result['categories']['artworks']['observed_bytes'], 0)
        for name in ('models', 'artworks'):
            self.assertIsNone(result['categories'][name]['bytes'])
        empty = self.models / 'empty'
        empty.mkdir()
        result = self.direct([('models', empty), ('artworks', empty)])
        self.assertEqual(result['status'], 'partial')
        self.assertTrue(any('範圍重疊' in item['message'] for item in result['issues']))

    def test_distinct_volumes_and_absent_empty_artworks(self):
        extra = self.root / 'extra'
        extra.mkdir()
        (self.models / 'one').write_bytes(b'123')
        (extra / 'two').write_bytes(b'12')
        self.artworks.rmdir()
        with patch.object(
            storage, 'volume_identity', side_effect=lambda path: (path.name, str(path))
        ):
            result = self.direct(
                [('models', self.models), ('models', extra), ('artworks', self.artworks)]
            )
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['categories']['models']['bytes'], 5)
        self.assertEqual(result['categories']['artworks']['bytes'], 0)
        self.assertFalse(self.artworks.exists())
        self.assertEqual(
            {row['id']: row['models'] for row in result['volumes']}, {'models': 3, 'extra': 2}
        )

    def test_reparse_and_disappearing_entries_are_skipped(self):
        loop = self.models / 'loop'
        loop.mkdir()
        (loop / 'not-read').write_bytes(b'skipped')
        vanished = self.models / 'vanished'
        vanished.touch()
        original = Path.lstat
        checked = []

        def inspect(path):
            checked.append(path)
            if path == vanished:
                raise FileNotFoundError()
            return original(path)

        was_link = categories.linked
        loop_inode = loop.lstat().st_ino
        with (
            patch.object(Path, 'lstat', inspect),
            patch.object(
                categories,
                'linked',
                side_effect=lambda info: info.st_ino == loop_inode or was_link(info),
            ),
        ):
            result = self.direct()
        self.assertNotIn(loop / 'not-read', checked)
        self.assertEqual(result['issue_count'], 2)
        self.assertEqual(result['categories']['models']['status'], 'partial')
        self.assertEqual(result['categories']['artworks']['status'], 'complete')
        with patch.object(categories, 'MAX_ENTRIES', 1):
            result = self.direct()
            self.assertEqual(result['visited'], 1)
            self.assertEqual(result['status'], 'partial')

    def test_container_preserves_reliable_artworks_from_partial_scan(self):
        (self.artworks / 'pic').write_bytes(b'art')
        with self.client(deployment_profile=Profile('container')) as client:
            report = self.wait(client, self.start(client), 'partial')
            self.assertTrue(report['scope']['external_engine'])
            self.assertEqual(report['scope']['unavailable'], ['models'])
            self.assertIsNone(report['scan']['categories']['models']['observed_bytes'])
            self.assertEqual(report['known']['artworks']['bytes'], 3)
            self.assertNotIn('models', report['known'])
            self.assertEqual(report['scan']['id'], report['last_result']['id'])

    def test_cancel_and_restart_preserve_cache(self):
        entered, cancelled = Event(), Event()

        def waiting(scope, stop, progress):
            progress(6)
            entered.set()
            stop.wait(5)
            cancelled.set()
            raise categories.Cancelled()

        with self.client() as client:
            first = self.wait(client, self.start(client), 'completed')
            with patch.object(categories, 'measure', waiting):
                identifier = self.start(client)
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.start(client), identifier)
                self.assertEqual(self.wait(client, identifier, 'running')['scan']['visited'], 6)
                self.assertEqual(
                    client.post(f'/api/storage/scans/{identifier}/cancel', json={}).status_code, 200
                )
                self.assertTrue(cancelled.wait(5))
                after = self.wait(client, identifier, 'cancelled')
                self.assertEqual(after['last_completed']['id'], first['scan']['id'])
                self.assertNotIn('categories', after['scan'])
            with patch.object(categories, 'measure', waiting):
                interrupted = self.start(client)
                self.wait(client, interrupted, 'running')
        with self.client() as client:
            report = self.wait(client, interrupted, 'failed')
            self.assertIn('重新啟動', report['scan']['error'])
            self.assertEqual(report['last_completed']['id'], first['scan']['id'])
            self.assertEqual(report['known']['models']['bytes'], 0)
