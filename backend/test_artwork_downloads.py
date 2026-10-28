import io
import zipfile
import unittest
from unittest.mock import patch
from uuid import uuid4

import httpx

from backend import gallery_api, test_api, test_gallery


class ArtworkDownloadTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    job = test_gallery.GalleryTests.job
    image = test_gallery.GalleryTests.image
    remote = test_gallery.GalleryTests.remote

    def seed(self):
        job, raw = self.job(('one.png', 'two.png')), self.image()
        with self.remote(lambda request: httpx.Response(200, content=raw)):
            response = self.client.post('/api/jobs/' + job['id'] + '/artworks')
        self.assertEqual(response.status_code, 200)
        return response.json()['imported'], raw

    def test_zip_contains_exact_originals_offline_without_changes(self):
        items, raw = self.seed()
        before = self.client.get('/api/artworks').json()
        with self.remote(lambda request: self.fail('must not contact engine')):
            response = self.client.post(
                '/api/artwork-downloads',
                json={
                    'artwork_ids': [item['id'] for item in items],
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], 'application/zip')
        self.assertIn('attachment;', response.headers['content-disposition'])
        self.assertEqual(int(response.headers['content-length']), len(response.content))
        with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
            self.assertEqual(bundle.namelist(), [item['id'] + '.png' for item in items])
            for name in bundle.namelist():
                self.assertEqual(bundle.read(name), raw)
        self.assertEqual(self.client.get('/api/artworks').json(), before)

    def test_missing_original_or_record_never_sends_partial_zip(self):
        items, _ = self.seed()
        target = self.db.parent / 'artworks' / (items[1]['id'] + '.png')
        target.unlink()
        response = self.client.post(
            '/api/artwork-downloads',
            json={
                'artwork_ids': [item['id'] for item in items],
            },
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn('未產生 ZIP', response.json()['detail'])
        self.assertEqual(
            self.client.post(
                '/api/artwork-downloads',
                json={
                    'artwork_ids': [items[0]['id'], str(uuid4())],
                },
            ).status_code,
            404,
        )
        self.assertEqual(len(self.client.get('/api/artworks').json()), 2)

    def test_identifiers_limits_and_size_are_bounded(self):
        items, _ = self.seed()
        for ids in [
            [],
            [items[0]['id']] * 2,
            [str(uuid4()) for _ in range(101)],
            ['../private'],
            ['C:\\secret.png'],
            [123],
        ]:
            with self.subTest(ids=str(ids)[:70]):
                self.assertEqual(
                    self.client.post(
                        '/api/artwork-downloads',
                        json={
                            'artwork_ids': ids,
                        },
                    ).status_code,
                    422,
                )
        with patch.object(gallery_api, 'MAX_DOWNLOAD_BYTES', 1):
            self.assertEqual(
                self.client.post(
                    '/api/artwork-downloads',
                    json={
                        'artwork_ids': [items[0]['id']],
                    },
                ).status_code,
                413,
            )

    def test_packaging_error_closes_temporary_file(self):
        items, _ = self.seed()
        temporary = io.BytesIO()
        with (
            patch.object(gallery_api.tempfile, 'SpooledTemporaryFile', return_value=temporary),
            patch.object(zipfile.ZipFile, 'write', side_effect=OSError('unreadable')),
        ):
            response = self.client.post(
                '/api/artwork-downloads',
                json={
                    'artwork_ids': [items[0]['id']],
                },
            )
        self.assertEqual(response.status_code, 409)
        self.assertTrue(temporary.closed)
